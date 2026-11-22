import type { Register } from 'claude-code'

type Rule = { kind: string; re: RegExp; group?: number }

const RULES: readonly Rule[] = [
  { kind: 'private-key', re: /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)/g },
  { kind: 'anthropic-key', re: /\bsk-ant-[A-Za-z0-9_-]{20,}/g },
  { kind: 'openai-key', re: /\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}/g },
  { kind: 'aws-access-key', re: /\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/g },
  { kind: 'github-token', re: /\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})/g },
  { kind: 'slack-token', re: /\bxox[abprs]-[A-Za-z0-9-]{10,}/g },
  { kind: 'stripe-key', re: /\b[sr]k_live_[A-Za-z0-9]{20,}/g },
  { kind: 'google-api-key', re: /\bAIza[0-9A-Za-z_-]{35}\b/g },
  { kind: 'npm-token', re: /\bnpm_[A-Za-z0-9]{36}\b/g },
  { kind: 'jwt', re: /\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/g },
  // secret = "value": only the value is replaced, and it must mix letters and digits.
  {
    kind: 'credential-assignment',
    re: /\b(?:api[_-]?key|secret|access[_-]?token|auth[_-]?token|password|passwd)["']?\s*[:=]\s*["']?((?=[A-Za-z0-9/+_.-]*\d)(?=[A-Za-z0-9/+_.-]*[A-Za-z])[A-Za-z0-9/+_.-]{16,})/gi,
    group: 1,
  },
]

const NETWORK = /\b(curl|wget|nc|ncat|scp|rsync|ssh|ftp|sftp|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)\b/i

/** Replace each secret with a labelled placeholder; return the text and the kinds found. */
export function redact(text: string): { text: string; kinds: string[] } {
  const kinds: string[] = []
  let out = text
  for (const { kind, re, group } of RULES) {
    out = out.replace(re, (...m) => {
      const whole = m[0] as string
      if (whole.includes('[REDACTED:')) return whole
      kinds.push(kind)
      const secret = group ? (m[group] as string) : whole
      return whole.replace(secret, `[REDACTED:${kind}]`)
    })
  }
  return { text: out, kinds: [...new Set(kinds)] }
}

/** Redact every string inside a tool's result, whatever its shape. */
function scrub(value: unknown, kinds: Set<string>): unknown {
  if (typeof value === 'string') {
    const found = redact(value)
    found.kinds.forEach(k => kinds.add(k))
    return found.text
  }
  if (Array.isArray(value)) return value.map(v => scrub(v, kinds))
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, scrub(v, kinds)]))
  }
  return value
}

/** What a tool brings back (file contents, command output) with secrets masked. */
function maskResult(ran: any): { ran: any; kinds: string[] } {
  if (ran.deny !== undefined) return { ran, kinds: [] }
  const kinds = new Set<string>()
  const result = scrub(ran.result, kinds)
  const context = scrub(ran.context, kinds)
  if (kinds.size === 0) return { ran, kinds: [] }
  return { ran: { ...ran, result, ...(ran.context ? { context } : {}) }, kinds: [...kinds] }
}

function isOutbound(tool: string, args: Record<string, unknown>): boolean {
  if (tool === 'WebFetch' || tool === 'WebSearch' || tool.startsWith('mcp__')) return true
  return tool === 'Bash' && NETWORK.test(String(args.command ?? ''))
}

export const register: Register = on => {
  on('prompt.submit', ($, e, next) => {
    if (e.command || e.isMeta) return next(e)
    const found = redact(e.text)
    if (found.kinds.length === 0) return next(e)
    $.ui.toast(`Redacted before sending: ${found.kinds.join(', ')}`)
    return next({ ...e, text: found.text })
  }).catch(() => ({ drop: 'outgoing-secret-guard failed while scanning, so the prompt was not sent. Try again, or disable the mod.' }))

  on('tool.call', async ($, e, next) => {
    const args = e as unknown as Record<string, unknown>
    if (!isOutbound(e.tool, args)) {
      const masked = maskResult(await next(e))
      if (masked.kinds.length) $.ui.toast(`Masked in tool output: ${masked.kinds.join(', ')}`)
      return masked.ran
    }
    const found = redact(JSON.stringify({ ...args, tool: undefined, tool_use_id: undefined }))
    if (found.kinds.length === 0) return next(e)
    $.ui.toast(`Blocked ${e.tool}: it carried ${found.kinds.join(', ')}`)
    return {
      deny: `${$.plugin.name}: this ${e.tool} call contains what looks like a secret (${found.kinds.join(', ')}) and would send it off the machine. Read it from an environment variable or file at run time instead of writing it into the call.`,
    }
  }).catch(($, e) => ({ deny: `${$.plugin.name}: the guard failed while scanning this call, so it was not run.` }))
}
