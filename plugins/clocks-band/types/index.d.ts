export type ItemKind = 'bash' | 'mcp' | 'subagent'

export type Item = {
  id: string
  kind: ItemKind
  label: string
  /** milliseconds on $.clock.now()'s clock when the mod saw the call start */
  startedAt: number
  /** the time to compare the elapsed time with, or null when there is none */
  limitMs: number | null
  /** 'limit' when the engine states it (a Bash timeout), 'warn' when it is our advisory time */
  limitKind: 'limit' | 'warn' | null
  /** a subagent's own id (kind 'subagent') */
  agentId?: string
  /** what a subagent is doing now: its latest tool call */
  doing?: { id: string; label: string; startedAt: number }
}

export type ClockState = { items: Item[]; tick: number }

declare module 'claude-code' {
  interface PluginState {
    'clocks-band': { clocks: ClockState }
  }
}
