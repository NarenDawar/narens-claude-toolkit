import { describe, expect, mock, test } from 'claude-code/testing'

import type { ClockState } from '../types'

const START = 1_000_000

// Session state stood in for beneath the plugin (the harness's $ has no state reader). Op-style stubs
// answer `{ value: <the call's result> }`.
const withState = (on: (name: string, hook: (...args: never[]) => unknown) => unknown) => {
  const store = { value: { items: [], tick: 0 } as ClockState, version: 0, writes: 0 }
  on('state.get', (() => ({ value: { value: store.value, version: store.version } })) as never)
  on('state.set', ((_: unknown, e: { value: ClockState; ifVersion?: number }) => {
    if (e.ifVersion !== undefined && e.ifVersion !== store.version) return { value: { isSet: false, version: store.version } }
    store.value = e.value
    store.version += 1
    store.writes += 1
    return { value: { isSet: true, version: store.version } }
  }) as never)
  return store
}

const OK = { result: {} as never, text: 'ok', isReadOnly: false }

// A tool call that stays pending until the test releases it.
const pending = (on: (name: string, hook: (...args: never[]) => unknown) => unknown) => {
  const releases: ((value: unknown) => void)[] = []
  on('tool.call', (() => new Promise(resolve => releases.push(resolve))) as never)
  return {
    release: (value: unknown = OK) => releases.shift()?.(value),
    count: () => releases.length,
  }
}

const ids = (store: { value: ClockState }) => store.value.items.map(item => item.id)

describe('tool calls', () => {
  test('a Bash call is listed while it runs and gone when it returns', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    const tool = pending(on as never)
    const call = $.tool.call({ tool: 'Bash', command: 'pytest -q', timeout: 600_000, tool_use_id: 'call-1' } as never)
    await clock.settle()
    expect(store.value.items).toEqual([
      { id: 'call-1', kind: 'bash', label: 'pytest -q', startedAt: START, limitMs: 600_000, limitKind: 'limit' },
    ])
    tool.release()
    await call
    await clock.settle()
    expect(store.value.items).toEqual([])
  })

  test('an MCP call is listed with its server and tool, with a warn time', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    const tool = pending(on as never)
    const call = $.tool.call({ tool: 'mcp__github__search_code', tool_use_id: 'm1' } as never)
    await clock.settle()
    expect(store.value.items[0]).toMatchObject({ kind: 'mcp', label: 'github.search_code', limitMs: 120_000, limitKind: 'warn' })
    tool.release()
    await call
  })

  test('other tools and background Bash commands are not listed', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    const tool = pending(on as never)
    const read = $.tool.call({ tool: 'Read', file_path: 'a.md' } as never)
    const background = $.tool.call({ tool: 'Bash', command: 'sleep 600', run_in_background: true } as never)
    await clock.settle()
    expect(store.value.items).toEqual([])
    expect(store.writes).toBeLessThanOrEqual(1) // only the one-time clean-up of rows an earlier load left
    tool.release()
    tool.release()
    await Promise.all([read, background])
  })

  test('parallel calls are separate items and end separately', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    const tool = pending(on as never)
    const one = $.tool.call({ tool: 'Bash', command: 'a', tool_use_id: 'c1' } as never)
    const two = $.tool.call({ tool: 'Bash', command: 'b', tool_use_id: 'c2' } as never)
    await clock.settle()
    expect(ids(store).sort()).toEqual(['c1', 'c2'])
    tool.release()
    await one
    await clock.settle()
    expect(ids(store)).toHaveLength(1)
    tool.release()
    await two
    await clock.settle()
    expect(ids(store)).toEqual([])
  })

  test('calls with no tool_use_id still get distinct ids', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    const tool = pending(on as never)
    const one = $.tool.call({ tool: 'Bash', command: 'a' } as never)
    const two = $.tool.call({ tool: 'Bash', command: 'b' } as never)
    await clock.settle()
    expect(new Set(ids(store)).size).toBe(2)
    tool.release()
    tool.release()
    await Promise.all([one, two])
  })

  test('a call that throws is removed and its error reaches the caller', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    let fail: (error: Error) => void = () => {}
    on('tool.call', (() => new Promise((_, reject) => { fail = reject })) as never)
    const call = $.tool.call({ tool: 'Bash', command: 'boom', tool_use_id: 'c1' } as never)
    await clock.settle()
    expect(ids(store)).toEqual(['c1'])
    fail(new Error('exploded'))
    await expect(call).rejects.toThrow()
    await clock.settle()
    expect(ids(store)).toEqual([])
  })

  test('the result of a call passes through exactly as it was', async ($, on) => {
    mock.clock(on as never, { now: START })
    withState(on as never)
    on('tool.call', (() => ({ result: { stdout: 'hi' }, text: 'hi', isError: true, isReadOnly: false })) as never)
    const result = await $.tool.call({ tool: 'Bash', command: 'false' } as never)
    expect(result).toEqual(expect.objectContaining({ text: 'hi', isError: true }))
  })

  test('a state write that never resolves does not hold up the call', async ($, on) => {
    mock.clock(on as never, { now: START })
    on('state.get', (() => ({ value: { value: { items: [], tick: 0 }, version: 0 } })) as never)
    on('state.set', (() => new Promise(() => {})) as never)
    on('tool.call', (() => OK) as never)
    const result = await $.tool.call({ tool: 'Bash', command: 'ls' } as never)
    expect(result).toEqual(expect.objectContaining({ text: 'ok' }))
  })

  test('a state write that throws does not break the call', async ($, on) => {
    mock.clock(on as never, { now: START })
    on('state.get', (() => { throw new Error('state down') }) as never)
    on('tool.call', (() => OK) as never)
    const result = await $.tool.call({ tool: 'Bash', command: 'ls' } as never)
    expect(result).toEqual(expect.objectContaining({ text: 'ok' }))
  })
})

describe('subagents', () => {
  test('a subagent is listed once it starts and removed on its turn.complete', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    on('agent.spawn', (() => ({ model: 'm', agentId: 'ag-1' })) as never)
    on('turn.complete', (() => ({ text: 'done' })) as never)
    await $.agent.spawn({ prompt: 'scan', description: 'scan the repo', subagentType: 'Explore', tool_use_id: 't1' } as never)
    await clock.settle()
    expect(store.value.items).toEqual([
      { id: 'agent:ag-1', kind: 'subagent', label: 'Explore: scan the repo', startedAt: START, limitMs: 600_000, limitKind: 'warn', agentId: 'ag-1' },
    ])
    await $.turn.complete({ answer: '', durationMs: 1, isAborted: false, turnId: 't', reason: 'answer', agentId: 'ag-1' } as never)
    await clock.settle()
    expect(store.value.items).toEqual([])
  })

  test('a spawn that was refused lists nothing', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    on('agent.spawn', (() => ({ deny: 'no' })) as never)
    await $.agent.spawn({ prompt: 'x', description: 'x', subagentType: 'Explore', tool_use_id: 't1' } as never)
    await clock.settle()
    expect(store.value.items).toEqual([])
  })

  test('a turn.complete without an agent id, or for another agent, leaves the list alone', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    on('agent.spawn', (() => ({ model: 'm', agentId: 'ag-1' })) as never)
    on('turn.complete', (() => ({ text: 'done' })) as never)
    await $.agent.spawn({ prompt: 'scan', description: 'd', subagentType: 'Explore', tool_use_id: 't1' } as never)
    await $.turn.complete({ answer: '', durationMs: 1, isAborted: false, turnId: 't', reason: 'answer' } as never)
    await $.turn.complete({ answer: '', durationMs: 1, isAborted: false, turnId: 't', reason: 'answer', agentId: 'other' } as never)
    await clock.settle()
    expect(ids(store)).toEqual(['agent:ag-1'])
  })

  test('the sweep drops a subagent the engine no longer reports as running', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    let status = 'running'
    on('agent.spawn', (() => ({ model: 'm', agentId: 'ag-1' })) as never)
    on('agent.list', (() => ({ value: [{ id: 'ag-1', description: 'd', type: 'Explore', status }] })) as never)
    await $.agent.spawn({ prompt: 'scan', description: 'd', subagentType: 'Explore', tool_use_id: 't1' } as never)
    await clock.advance(1000)
    expect(ids(store)).toEqual(['agent:ag-1'])
    status = 'killed'
    await clock.advance(1000)
    expect(ids(store)).toEqual([])
    const after = store.value.tick
    await clock.advance(5000)
    expect(store.value.tick).toBe(after)
  })

  test('a subagent row shows the latest tool call of that subagent while it runs', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    on('agent.spawn', (() => ({ model: 'm', agentId: 'ag-1' })) as never)
    const tool = pending(on as never)
    await $.agent.spawn({ prompt: 'scan', description: 'd', subagentType: 'Explore', tool_use_id: 't1' } as never)
    const call = $.tool.call({ tool: 'Bash', command: 'pytest', tool_use_id: 'c1', agentId: 'ag-1' } as never)
    await clock.settle()
    const agent = store.value.items.find(item => item.kind === 'subagent')
    expect(agent?.doing).toEqual({ id: 'c1', label: 'pytest', startedAt: START })
    tool.release()
    await call
    await clock.settle()
    expect(store.value.items.find(item => item.kind === 'subagent')?.doing).toBeUndefined()
  })
})

describe('clearing', () => {
  test('/clear and /resume empty the list; other session ends do not', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    on('session.end', ((_: unknown, e: { sessionId: string }) => ({ sessionId: e.sessionId })) as never)
    const tool = pending(on as never)
    void $.tool.call({ tool: 'Bash', command: 'a', tool_use_id: 'c1' } as never)
    await clock.settle()
    expect(ids(store)).toEqual(['c1'])
    await $.session.end({ reason: 'exit', sessionId: 's1', resume: { id: 's1' } } as never)
    await clock.settle()
    expect(ids(store)).toEqual(['c1'])
    await $.session.end({ reason: 'clear', sessionId: 's1', resume: { id: 's1' } } as never)
    await clock.settle()
    expect(ids(store)).toEqual([])
    tool.release()
  })
})

describe('the tick', () => {
  test('it runs once a second while something is listed, and stops when the list is empty', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    const tool = pending(on as never)
    const call = $.tool.call({ tool: 'Bash', command: 'a', tool_use_id: 'c1' } as never)
    await clock.settle()
    const before = store.value.tick
    await clock.advance(3000)
    expect(store.value.tick - before).toBe(3)
    tool.release()
    await call
    await clock.settle()
    const after = store.value.tick
    await clock.advance(5000)
    expect(store.value.tick).toBe(after)
  })

  test('parallel starts share one tick', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    const tool = pending(on as never)
    const one = $.tool.call({ tool: 'Bash', command: 'a', tool_use_id: 'c1' } as never)
    const two = $.tool.call({ tool: 'Bash', command: 'b', tool_use_id: 'c2' } as never)
    await clock.settle()
    const before = store.value.tick
    await clock.advance(2000)
    expect(store.value.tick - before).toBe(2)
    tool.release()
    tool.release()
    await Promise.all([one, two])
  })

  test('/clear stops the tick', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    on('session.end', ((_: unknown, e: { sessionId: string }) => ({ sessionId: e.sessionId })) as never)
    const tool = pending(on as never)
    void $.tool.call({ tool: 'Bash', command: 'a', tool_use_id: 'c1' } as never)
    await clock.settle()
    await $.session.end({ reason: 'clear', sessionId: 's1', resume: { id: 's1' } } as never)
    await clock.settle()
    const after = store.value.tick
    await clock.advance(5000)
    expect(store.value.tick).toBe(after)
    tool.release()
  })
})

describe('review fixes', () => {
  test('a clock.now that never answers does not hold up a tool call', async ($, on) => {
    on('clock.now', (() => new Promise(() => {})) as never)
    withState(on as never)
    on('tool.call', (() => OK) as never)
    const result = await $.tool.call({ tool: 'Bash', command: 'ls', tool_use_id: 'c1' } as never)
    expect(result).toEqual(expect.objectContaining({ text: 'ok' }))
  })

  test('a clock.now that never answers does not hold up a subagent spawn', async ($, on) => {
    on('clock.now', (() => new Promise(() => {})) as never)
    withState(on as never)
    on('agent.spawn', (() => ({ model: 'm', agentId: 'ag-1' })) as never)
    const result = await $.agent.spawn({ prompt: 'x', description: 'x', subagentType: 'Explore', tool_use_id: 't1' } as never)
    expect(result).toEqual(expect.objectContaining({ agentId: 'ag-1' }))
  })

  test('a state write that never resolves does not hold up /clear', async ($, on) => {
    mock.clock(on as never, { now: START })
    on('state.get', (() => ({ value: { value: { items: [], tick: 0 }, version: 0 } })) as never)
    on('state.set', (() => new Promise(() => {})) as never)
    on('session.end', ((_: unknown, e: { sessionId: string }) => ({ sessionId: e.sessionId })) as never)
    await $.session.end({ reason: 'clear', sessionId: 's1', resume: { id: 's1' } } as never)
  })

  test('rows left in state by an earlier load are dropped on the first event', async ($, on) => {
    const clock = mock.clock(on as never, { now: START })
    const store = withState(on as never)
    store.value = {
      items: [{ id: 'old', kind: 'bash', label: 'left behind', startedAt: 0, limitMs: null, limitKind: null }],
      tick: 0,
    }
    on('tool.call', (() => OK) as never)
    await $.tool.call({ tool: 'Read', file_path: 'a.md' } as never)
    await clock.settle()
    expect(ids(store)).toEqual([])
  })

  test(
    'a call a hook above gives up on is removed when its dispatch is abandoned',
    {
      plugins: [
        {
          name: 'impatient',
          tier: 'prepend',
          register(on) {
            on('tool.call', async ($, e, next) =>
              Promise.race([next(e), $.clock.sleep(1000).then(() => ({ deny: 'too slow' }))]) as never)
          },
        },
      ],
    },
    async ($, on) => {
      const clock = mock.clock(on as never, { now: START })
      const store = withState(on as never)
      on('tool.call', (() => new Promise(() => {})) as never)
      const call = $.tool.call({ tool: 'Bash', command: 'sleep 99', tool_use_id: 'c1' } as never)
      await clock.settle()
      expect(ids(store)).toEqual(['c1'])
      await clock.advance(1000)
      await call
      await clock.settle()
      expect(ids(store)).toEqual([])
    },
  )
})
