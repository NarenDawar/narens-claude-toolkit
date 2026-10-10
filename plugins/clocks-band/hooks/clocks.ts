import type { Item, ItemKind } from '../types'

export type Options = {
  minSeconds: number
  maxRows: number
  subagentWarnMinutes: number
  mcpWarnSeconds: number
  bashDefaultLimitSeconds: number
}

export const DEFAULTS: Options = {
  minSeconds: 5,
  maxRows: 4,
  subagentWarnMinutes: 10,
  mcpWarnSeconds: 120,
  bashDefaultLimitSeconds: 0,
}

const RANGES: Record<keyof Options, readonly [number, number]> = {
  minSeconds: [1, 600],
  maxRows: [1, 20],
  subagentWarnMinutes: [1, 1440],
  mcpWarnSeconds: [1, 86400],
  bashDefaultLimitSeconds: [0, 3600],
}

/** The settings, each kept only when it is a finite number in its range; anything else is the default. */
export const readOptions = (raw: Readonly<Record<string, unknown>>): Options => {
  const out: Options = { ...DEFAULTS }
  for (const key of Object.keys(RANGES) as (keyof Options)[]) {
    const value = raw[key]
    const [low, high] = RANGES[key]
    if (typeof value === 'number' && Number.isFinite(value) && value >= low && value <= high) {
      out[key] = value
    }
  }
  out.maxRows = Math.floor(out.maxRows)
  return out
}

/** One line of safe text: control characters become visible escapes, whitespace collapses, long text is cut. */
export const escapeText = (text: string, max: number): string => {
  const flat = String(text)
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/[\u0000-\u001f\u007f-\u009f]/g, char => `\\x${char.charCodeAt(0).toString(16).padStart(2, '0')}`)
    .replace(/ {2,}/g, ' ')
    .trim()
  const chars = Array.from(flat)
  return chars.length <= max ? flat : chars.slice(0, Math.max(0, max - 1)).join('') + '…'
}

export const formatDuration = (ms: number): string => {
  const total = Math.max(0, Math.floor((Number.isFinite(ms) ? ms : 0) / 1000))
  if (total < 60) return `${total}s`
  const minutes = Math.floor(total / 60)
  if (minutes < 60) return `${minutes}m${String(total % 60).padStart(2, '0')}s`
  return `${Math.floor(minutes / 60)}h${String(minutes % 60).padStart(2, '0')}m`
}

export const kindOfTool = (tool: string): 'bash' | 'mcp' | null =>
  tool === 'Bash' ? 'bash' : tool.startsWith('mcp__') ? 'mcp' : null

const LABEL_MAX = 60

export const labelFor = (
  kind: ItemKind,
  input: { command?: unknown; tool?: unknown; subagentType?: unknown; description?: unknown },
): string => {
  if (kind === 'bash') {
    const text = typeof input.command === 'string' ? escapeText(input.command, LABEL_MAX) : ''
    return text === '' ? 'Bash' : text
  }
  if (kind === 'mcp') {
    const tool = typeof input.tool === 'string' ? input.tool : ''
    const parts = tool.startsWith('mcp__') ? tool.slice(5).split('__') : []
    const server = parts.shift() ?? ''
    const name = parts.join('__')
    const label = name === '' ? server : `${server}.${name}`
    return label === '' ? 'mcp' : escapeText(label, LABEL_MAX)
  }
  const type = typeof input.subagentType === 'string' && input.subagentType !== '' ? input.subagentType : 'agent'
  const description = typeof input.description === 'string' ? input.description.trim() : ''
  return escapeText(description === '' ? type : `${type}: ${description}`, LABEL_MAX)
}

/** The time to compare with: a Bash timeout (milliseconds) is a limit; subagent and MCP times are advisory warns. */
export const limitFor = (
  kind: ItemKind,
  input: { timeout?: unknown },
  options: Options,
): { limitMs: number | null; limitKind: 'limit' | 'warn' | null } => {
  if (kind === 'bash') {
    const timeout = input.timeout
    if (typeof timeout === 'number' && Number.isFinite(timeout) && timeout > 0) {
      return { limitMs: timeout, limitKind: 'limit' }
    }
    if (options.bashDefaultLimitSeconds > 0) {
      return { limitMs: options.bashDefaultLimitSeconds * 1000, limitKind: 'limit' }
    }
    return { limitMs: null, limitKind: null }
  }
  if (kind === 'mcp') {
    return { limitMs: options.mcpWarnSeconds * 1000, limitKind: 'warn' }
  }
  return { limitMs: options.subagentWarnMinutes * 60_000, limitKind: 'warn' }
}

export const addItem = (items: readonly Item[], item: Item): Item[] =>
  items.some(existing => existing.id === item.id)
    ? items.map(existing => (existing.id === item.id ? item : existing))
    : [...items, item]

export const removeItem = (items: readonly Item[], id: string): Item[] => items.filter(item => item.id !== id)

export const endAgent = (items: readonly Item[], agentId: string): Item[] =>
  items.filter(item => !(item.kind === 'subagent' && item.agentId === agentId))

export const setDoing = (items: readonly Item[], agentId: string, doing: NonNullable<Item['doing']>): Item[] =>
  items.map(item => (item.kind === 'subagent' && item.agentId === agentId ? { ...item, doing } : item))

export const clearDoing = (items: readonly Item[], agentId: string, doingId: string): Item[] =>
  items.map(item => {
    if (item.kind === 'subagent' && item.agentId === agentId && item.doing?.id === doingId) {
      const { doing: _gone, ...rest } = item
      return rest
    }
    return item
  })

export type Row = Item & { elapsedMs: number; over: boolean }

export const visibleRows = (
  items: readonly Item[],
  now: number,
  options: Options,
): { rows: Row[]; more: number } => {
  const qualifying = items
    .map(item => {
      const elapsedMs = Math.max(0, now - item.startedAt)
      return { ...item, elapsedMs, over: item.limitMs !== null && elapsedMs >= item.limitMs }
    })
    .filter(row => row.elapsedMs >= options.minSeconds * 1000)
    .sort((a, b) => b.elapsedMs - a.elapsedMs || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
  return { rows: qualifying.slice(0, options.maxRows), more: Math.max(0, qualifying.length - options.maxRows) }
}

const TAG: Record<ItemKind, string> = { bash: 'Bash', mcp: 'mcp', subagent: 'subagent' }
const TAG_WIDTH = 9
const MIN_LABEL = 8

const timeText = (row: Row): string =>
  formatDuration(row.elapsedMs) +
  (row.limitMs !== null ? ` / ${formatDuration(row.limitMs)} ${row.limitKind}` : '') +
  (row.over ? '  OVER' : '')

/** The band's lines. The label gives way first on a narrow width; the times are never cut. */
export const formatRows = (rows: readonly Row[], more: number, now: number, width: number): string[] => {
  if (rows.length === 0 && more === 0) return []
  const times = rows.map(timeText)
  const timeWidth = Math.max(0, ...times.map(text => text.length))
  const labels = rows.map(row =>
    row.doing ? `${row.label} → ${row.doing.label} ${formatDuration(now - row.doing.startedAt)}` : row.label,
  )
  const room = Math.max(MIN_LABEL, width - TAG_WIDTH - 2 - timeWidth)
  const labelWidth = Math.min(room, Math.max(0, ...labels.map(label => Array.from(label).length)))
  const lines = rows.map((row, index) => {
    const label = escapeText(labels[index], labelWidth)
    return `${TAG[row.kind].padEnd(TAG_WIDTH)}${label.padEnd(labelWidth)}  ${times[index]}`
  })
  if (more > 0) lines.push(`+${more} more`)
  return lines
}
