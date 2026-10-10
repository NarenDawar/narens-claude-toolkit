import { describe, expect, mock, test } from 'claude-code/testing'

import type { ClockState, Item } from '../types'

const NOW = 2_000_000

const withState = (
  on: (name: string, hook: (...args: never[]) => unknown) => unknown,
  initial: ClockState,
) => {
  const store = { value: initial, version: 0 }
  on('state.get', (() => ({ value: { value: store.value, version: store.version } })) as never)
  on('state.set', ((_: unknown, e: { value: ClockState }) => {
    store.value = e.value
    store.version += 1
    return { value: { isSet: true, version: store.version } }
  }) as never)
  // What the engine draws when no plugin does, so a band that stays out of the way leaves this showing.
  on('ui.render', (($: any, e: any) => {
    const { Text } = $.ui.resolve(e)
    return <Text>ENGINE-DRAWS</Text>
  }) as never)
  return store
}

const bashItem = (over: Partial<Item> = {}): Item => ({
  id: 'c1',
  kind: 'bash',
  label: 'pytest -q tests/',
  startedAt: NOW - 130_000,
  limitMs: 600_000,
  limitKind: 'limit',
  ...over,
})

const PROPS = {
  hasSurvey: false,
  isWorking: true,
  maxRows: 12,
  bodyColumns: 100,
  scroll: { top: 0, bodyRows: 12 },
} as never

type Mounted = { findAll: (query: unknown) => Promise<{ text?: string }[]>; drawn: () => Promise<unknown> }

const mount = ($: unknown, surface: 'terminal' | 'desktop', props: unknown = PROPS): Promise<Mounted> =>
  ($ as { ui: { mount: (target: unknown) => Promise<Mounted> } }).ui.mount({
    plugin: 'clocks-band',
    surface,
    component: 'AbovePrompt',
    props,
  })

const textOf = async (mounted: Mounted): Promise<string> => JSON.stringify(await mounted.drawn())

for (const surface of ['terminal', 'desktop'] as const) {
  describe(`the band on ${surface}`, () => {
    test('nothing long-running draws nothing of its own', async ($, on) => {
      mock.clock(on as never, { now: NOW })
      withState(on as never, { items: [bashItem({ startedAt: NOW - 1000 })], tick: 0 })
      const text = await textOf(await mount($, surface))
      expect(text).not.toContain('pytest')
      expect(text).toContain('ENGINE-DRAWS')
    })

    test('a long-running item is drawn with its time and its limit', async ($, on) => {
      mock.clock(on as never, { now: NOW })
      withState(on as never, { items: [bashItem()], tick: 0 })
      const text = await textOf(await mount($, surface))
      expect(text).toContain('Bash')
      expect(text).toContain('pytest -q tests/')
      expect(text).toContain('2m10s / 10m00s limit')
      expect(text).not.toContain('OVER')
      expect(text).not.toContain('red')
    })

    test('an item at its limit says OVER', async ($, on) => {
      mock.clock(on as never, { now: NOW })
      withState(on as never, { items: [bashItem({ startedAt: NOW - 600_000 })], tick: 0 })
      const text = await textOf(await mount($, surface))
      expect(text).toContain('OVER')
      expect(text).toContain('red')
    })

    test('warn and limit are worded differently', async ($, on) => {
      mock.clock(on as never, { now: NOW })
      withState(on as never, {
        items: [
          bashItem({ id: 'a' }),
          { id: 'agent:1', kind: 'subagent', label: 'Explore: scan', startedAt: NOW - 222_000, limitMs: 600_000, limitKind: 'warn', agentId: '1' },
        ],
        tick: 0,
      })
      const text = await textOf(await mount($, surface))
      expect(text).toContain('limit')
      expect(text).toContain('warn')
    })

    test('more rows than the cap end with +N more', async ($, on) => {
      mock.clock(on as never, { now: NOW })
      const items = Array.from({ length: 6 }, (_, i) => bashItem({ id: `c${i}`, label: `job ${i}`, startedAt: NOW - (10 + i) * 1000 }))
      withState(on as never, { items, tick: 0 })
      const text = await textOf(await mount($, surface))
      expect(text).toContain('+2 more')
      expect(text).not.toContain('job 0')
    })

    test('a survey holding the band is left alone', async ($, on) => {
      mock.clock(on as never, { now: NOW })
      withState(on as never, { items: [bashItem()], tick: 0 })
      const text = await textOf(await mount($, surface, { ...(PROPS as object), hasSurvey: true }))
      expect(text).not.toContain('pytest')
      expect(text).toContain('ENGINE-DRAWS')
    })

    test('hostile labels are drawn as escaped text, never raw control characters', async ($, on) => {
      mock.clock(on as never, { now: NOW })
      // the label as the pure module stores it: already escaped
      withState(on as never, { items: [bashItem({ label: 'echo \\x1b[2J' })], tick: 0 })
      const text = await textOf(await mount($, surface))
      expect(text).not.toContain('\x1b')
      expect(text).toContain('echo')
    })

    test('a narrow band keeps the times', async ($, on) => {
      mock.clock(on as never, { now: NOW })
      withState(on as never, { items: [bashItem({ label: 'x'.repeat(50) })], tick: 0 })
      const text = await textOf(await mount($, surface, { ...(PROPS as object), bodyColumns: 40 }))
      expect(text).toContain('2m10s / 10m00s limit')
    })
  })
}

describe('the band and its settings', () => {
  test('minSeconds and maxRows come from the settings', async ($, on) => {
    mock.clock(on as never, { now: NOW })
    const items = [bashItem({ id: 'a', label: 'old', startedAt: NOW - 20_000 }), bashItem({ id: 'b', label: 'young', startedAt: NOW - 12_000 })]
    withState(on as never, { items, tick: 0 })
    const text = await textOf(await mount($, 'terminal'))
    expect(text).toContain('old')
    expect(text).toContain('young')
  })

  test('maxRows from the settings caps the rows', { options: { minSeconds: 15, maxRows: 1 } }, async ($, on) => {
    mock.clock(on as never, { now: NOW })
    const items = [bashItem({ id: 'a', label: 'old', startedAt: NOW - 20_000 }), bashItem({ id: 'b', label: 'young', startedAt: NOW - 12_000 })]
    withState(on as never, { items, tick: 0 })
    const text = await textOf(await mount($, 'terminal'))
    expect(text).toContain('old')
    expect(text).not.toContain('young')
  })

  test('a failing state read leaves the band empty instead of throwing', async ($, on) => {
    mock.clock(on as never, { now: NOW })
    on('state.get', (() => { throw new Error('state down') }) as never)
    on('ui.render', (($: any, e: any) => {
      const { Text } = $.ui.resolve(e)
      return <Text>ENGINE-DRAWS</Text>
    }) as never)
    const text = await textOf(await mount($, 'terminal'))
    expect(text).not.toContain('Bash')
    expect(text).toContain('ENGINE-DRAWS')
  })
})
