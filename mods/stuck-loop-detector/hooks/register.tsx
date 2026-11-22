import type { Register } from 'claude-code'

// Calls that change files or the world reset the history: re-running a test
// after an edit is progress, not a loop.
const CHANGES_STATE = new Set(['Edit', 'MultiEdit', 'Write', 'NotebookEdit'])
const WINDOW = 12
const REPEAT_AT = 3 // the same call this many times in a row
const BOUNCE_AT = 6 // A,B,A,B,A,B

const IGNORED = new Set(['tool', 'tool_use_id', 'agentId', 'requestMeta'])

export function signature(e: Record<string, unknown>): string {
  const keep = Object.keys(e)
    .filter(k => !IGNORED.has(k))
    .sort()
    .map(k => [k, e[k]])
  return `${String(e.tool)}:${JSON.stringify(keep)}`
}

/** What the recent calls of one loop say: a repeat count, or a two-call bounce. */
export function diagnose(history: readonly string[]): { kind: 'repeat' | 'bounce'; count: number } | null {
  const last = history[history.length - 1]
  if (last === undefined) return null
  let run = 0
  for (let i = history.length - 1; i >= 0 && history[i] === last; i--) run++
  if (run >= REPEAT_AT) return { kind: 'repeat', count: run }

  const tail = history.slice(-BOUNCE_AT)
  const isBounce =
    tail.length === BOUNCE_AT &&
    tail[0] !== tail[1] &&
    tail.every((s, i) => s === tail[i % 2])
  return isBounce ? { kind: 'bounce', count: BOUNCE_AT } : null
}

// Warn on the first hit, then every second call after, so a long loop is not nagged each time.
export function shouldWarn(found: { kind: string; count: number }): boolean {
  const first = found.kind === 'repeat' ? REPEAT_AT : BOUNCE_AT
  return found.count >= first && (found.count - first) % 2 === 0
}

export const register: Register = on => {
  const histories = new Map<string, string[]>()

  on('prompt.submit', ($, e, next) => {
    histories.clear()
    $.ui.status(undefined)
    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const loop = e.agentId ?? 'main'
    const history = histories.get(loop) ?? []
    if (CHANGES_STATE.has(e.tool)) {
      history.length = 0
    } else {
      history.push(signature(e as Record<string, unknown>))
      if (history.length > WINDOW) history.shift()
    }
    histories.set(loop, history)

    const found = diagnose(history)
    if (!found) {
      $.ui.status(undefined)
      return next(e)
    }

    const label = `${e.tool} ${found.kind === 'repeat' ? `x${found.count}` : 'bouncing'}`
    $.ui.status(`loop? ${label}`)
    const ran = await next(e)
    if (!shouldWarn(found) || ran.deny !== undefined) return ran

    $.ui.toast(`Possible loop: ${label}`)
    const note =
      found.kind === 'repeat'
        ? `${$.plugin.name}: this exact ${e.tool} call has now run ${found.count} times in a row with the same arguments and no edit in between. Repeating it will not change the outcome. Stop, say what you expected and what you got, and try a different approach or ask the user.`
        : `${$.plugin.name}: the last ${found.count} tool calls alternate between the same two calls with no edit in between. This looks like a loop. Stop, say what is not working, and try a different approach or ask the user.`
    return { ...ran, context: [...(ran.context ?? []), note] }
  }).catch(($, e, next) => next(e))
}
