import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { ClockState, Item } from '../types'
import {
  addItem,
  clearDoing,
  endAgent,
  formatRows,
  kindOfTool,
  labelFor,
  limitFor,
  readOptions,
  removeItem,
  setDoing,
  visibleRows,
} from './clocks'

const EMPTY: ClockState = { items: [], tick: 0 }

export const clocksAtom = atom({ plugin: 'clocks-band', key: 'clocks' } as const, EMPTY)

type Hooked = Parameters<Parameters<Parameters<Register>[0]>[2]>[0]

// Ids this load of the module has added. State survives a hot reload but this module's variables do
// not, so on the first event after a load, rows it did not add are left over from an earlier load.
const mine = new Set<string>()
let fresh = false
let counter = 0
let timer: { cancel: () => void } | null = null

// The mod only watches: everything below is fire-and-forget and swallows its own failures, so a
// slow, failing or hung state write can never hold up or break a tool call.
const quietly = (work: Promise<unknown>): void => {
  work.catch(() => {})
}

const stopTimer = (): void => {
  timer?.cancel()
  timer = null
}

// One tick: drop subagents the engine no longer reports as running, and bump the tick so the band redraws.
const sweep = async ($: Hooked): Promise<void> => {
  let alive: Set<string> | null = null
  let known: Set<string> | null = null
  try {
    const agents = await $.agent.list()
    known = new Set(agents.map(agent => agent.id))
    alive = new Set(agents.filter(agent => agent.status === 'running').map(agent => agent.id))
  } catch {
    // keep what we have
  }
  const next = await update($, clocksAtom, state => ({
    items: state.items.filter(
      item =>
        item.kind !== 'subagent' ||
        item.agentId === undefined ||
        known === null ||
        !known.has(item.agentId) ||
        (alive !== null && alive.has(item.agentId)),
    ),
    tick: state.tick + 1,
  }))
  if (next.items.length === 0) stopTimer()
}

const startTimer = ($: Hooked): void => {
  if (timer !== null) return
  timer = $.clock.every(1000, () => {
    quietly(sweep($))
  })
}

const freshen = async ($: Hooked): Promise<void> => {
  if (fresh) return
  fresh = true
  await update($, clocksAtom, state => ({ ...state, items: state.items.filter(item => mine.has(item.id)) }))
}

// The start time is asked for at once but only awaited off the call's path.
const record = async ($: Hooked, started: Promise<number>, make: (startedAt: number) => Item, then?: (item: Item) => Promise<unknown>): Promise<void> => {
  const item = make(await started)
  await add($, item)
  if (then) await then(item)
}

const add = async ($: Hooked, item: Item): Promise<void> => {
  await update($, clocksAtom, state => ({ ...state, items: addItem(state.items, item) }))
  startTimer($)
}

const change = async ($: Hooked, edit: (items: readonly Item[]) => Item[]): Promise<void> => {
  const next = await update($, clocksAtom, state => ({ ...state, items: edit(state.items) }))
  if (next.items.length === 0) stopTimer()
}

export const register: Register = (on, rawOptions) => {
  const options = readOptions(rawOptions)
  on('tool.call', async ($, e, next) => {
    quietly(freshen($))
    const kind = kindOfTool(e.tool)
    const input = e as unknown as { command?: unknown; timeout?: unknown; run_in_background?: unknown }
    if (kind === null || input.run_in_background === true) {
      return next(e)
    }
    const id = e.tool_use_id
    const agentId = (e as { agentId?: string }).agentId
    mine.add(id)
    const label = labelFor(kind, { command: input.command, tool: e.tool })
    const limit = limitFor(kind, input, options)
    let added: Promise<unknown> = Promise.resolve()
    try {
      const started = $.clock.now()
      started.catch(() => {})
      added = record(
        $,
        started,
        startedAt => ({ id, kind, label, startedAt, ...limit }),
        item => (agentId === undefined ? undefined : change($, items => setDoing(items, agentId, { id, label, startedAt: item.startedAt }))),
      ).catch(() => {})
    } catch {
      // not recorded; the call proceeds as if the mod were not there
    }
    const remove = (): void => {
      quietly(added.then(() => change($, items => clearDoing(removeItem(items, id), agentId ?? '', id))))
    }
    try {
      next.signal.addEventListener('abort', remove, { once: true })
    } catch {
      // no signal to listen to; the finally below still covers calls that settle
    }
    try {
      return await next(e)
    } finally {
      remove()
    }
  })

  on('agent.spawn', async ($, e, next) => {
    quietly(freshen($))
    const result = await next(e)
    try {
      const agentId = result.agentId
      if (agentId !== undefined) {
        const id = `agent:${agentId}`
        mine.add(id)
        const started = $.clock.now()
        started.catch(() => {})
        const label = labelFor('subagent', { subagentType: e.subagentType, description: e.description })
        const limit = limitFor('subagent', {}, options)
        quietly(record($, started, startedAt => ({ id, kind: 'subagent', label, startedAt, ...limit, agentId })))
      }
    } catch {
      // the spawn is untouched
    }
    return result
  })

  on('turn.complete', async ($, e, next) => {
    quietly(freshen($))
    const result = await next(e)
    try {
      const agentId = (e as { agentId?: string }).agentId
      if (agentId !== undefined) {
        quietly(change($, items => endAgent(items, agentId)))
      }
    } catch {
      // the turn is untouched
    }
    return result
  })

  on('session.end', async ($, e, next) => {
    // /clear and /resume end the conversation while the process goes on under another session.
    if (e.reason === 'clear' || e.reason === 'resume') {
      try {
        stopTimer()
        mine.clear()
        quietly(update($, clocksAtom, () => EMPTY))
      } catch {
        // never break the session
      }
    }
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    try {
      const props = e.props as { hasSurvey?: boolean; bodyColumns?: number }
      if (props.hasSurvey) return next(e)
      const state = await read($, clocksAtom)
      const now = await $.clock.now()
      const { rows, more } = visibleRows(state.items, now, options)
      if (rows.length === 0) return next(e)
      const lines = formatRows(rows, more, now, typeof props.bodyColumns === 'number' ? props.bodyColumns : 100)
      const { Box, Text } = $.ui.resolve(e)
      return (
        <Box flexDirection="column">
          {lines.map((line, index) => (
            <Text key={index} wrap="truncate" color={line.includes('  OVER') ? 'red' : undefined} dimColor={!line.includes('  OVER')}>
              {line}
            </Text>
          ))}
        </Box>
      )
    } catch {
      return next(e)
    }
  })
}
