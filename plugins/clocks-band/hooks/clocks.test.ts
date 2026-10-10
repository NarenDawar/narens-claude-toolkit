import { describe, expect, test } from 'claude-code/testing'

import type { Item } from '../types'
import {
  addItem,
  clearDoing,
  DEFAULTS,
  endAgent,
  escapeText,
  formatDuration,
  formatRows,
  kindOfTool,
  labelFor,
  limitFor,
  readOptions,
  removeItem,
  setDoing,
  visibleRows,
} from './clocks'

const item = (over: Partial<Item> = {}): Item => ({
  id: 'a',
  kind: 'bash',
  label: 'pytest',
  startedAt: 0,
  limitMs: null,
  limitKind: null,
  ...over,
})

describe('readOptions', () => {
  test('missing or good values are kept, bad ones fall back', () => {
    expect(readOptions({})).toEqual(DEFAULTS)
    expect(readOptions({ minSeconds: 10, maxRows: 6, subagentWarnMinutes: 3, mcpWarnSeconds: 30, bashDefaultLimitSeconds: 120 })).toEqual({
      minSeconds: 10,
      maxRows: 6,
      subagentWarnMinutes: 3,
      mcpWarnSeconds: 30,
      bashDefaultLimitSeconds: 120,
    })
    expect(readOptions({ minSeconds: '5', maxRows: NaN, subagentWarnMinutes: -1, mcpWarnSeconds: Infinity, bashDefaultLimitSeconds: 99999 })).toEqual(DEFAULTS)
    expect(readOptions({ minSeconds: 0, maxRows: 99, mcpWarnSeconds: 0 })).toEqual(DEFAULTS)
  })

  test('maxRows is a whole number', () => {
    expect(readOptions({ maxRows: 3.7 }).maxRows).toBe(3)
  })

  test('0 is a valid bashDefaultLimitSeconds (no limit)', () => {
    expect(readOptions({ bashDefaultLimitSeconds: 0 }).bashDefaultLimitSeconds).toBe(0)
  })
})

describe('formatDuration', () => {
  test('seconds, minutes and hours', () => {
    expect(formatDuration(0)).toBe('0s')
    expect(formatDuration(59_999)).toBe('59s')
    expect(formatDuration(60_000)).toBe('1m00s')
    expect(formatDuration(125_000)).toBe('2m05s')
    expect(formatDuration(3_599_000)).toBe('59m59s')
    expect(formatDuration(3_600_000)).toBe('1h00m')
    expect(formatDuration(3_725_000)).toBe('1h02m')
  })

  test('negative and non-finite values read as 0s', () => {
    expect(formatDuration(-5)).toBe('0s')
    expect(formatDuration(NaN)).toBe('0s')
    expect(formatDuration(Infinity)).toBe('0s')
  })
})

describe('escapeText', () => {
  test('control characters are visible escapes, whitespace collapses, long text is cut', () => {
    expect(escapeText('a\x1b[2Jb', 40)).toBe('a\\x1b[2Jb')
    expect(escapeText('line1\nline2\t\ttab\r\n', 40)).toBe('line1 line2 tab')
    expect(escapeText('  a    b  ', 40)).toBe('a b')
    expect(escapeText('x'.repeat(100), 10)).toBe('x'.repeat(9) + '…')
    expect(escapeText('short', 10)).toBe('short')
    expect(escapeText('', 10)).toBe('')
  })

  test('a cut never splits an emoji', () => {
    const text = '\u{1F600}'.repeat(20)
    const cut = escapeText(text, 5)
    expect(Array.from(cut).length).toBe(5)
    expect(cut.endsWith('…')).toBe(true)
    expect(cut).not.toMatch(/[\ud800-\udbff](?![\udc00-\udfff])/)
  })
})

describe('kindOfTool', () => {
  test('Bash and mcp__ tools are tracked, everything else is not', () => {
    expect(kindOfTool('Bash')).toBe('bash')
    expect(kindOfTool('mcp__github__search_code')).toBe('mcp')
    for (const tool of ['Read', 'Edit', 'Agent', 'Task', 'WebFetch', 'bash', 'mcp_github', '']) {
      expect(kindOfTool(tool)).toBe(null)
    }
  })
})

describe('labelFor', () => {
  test('bash: the command, one line, cut', () => {
    expect(labelFor('bash', { command: 'pytest -q tests/' })).toBe('pytest -q tests/')
    expect(labelFor('bash', { command: 'cd app &&\n  npm test' })).toBe('cd app && npm test')
    expect(labelFor('bash', { command: 'x'.repeat(200) }).length).toBeLessThanOrEqual(60)
    expect(labelFor('bash', { command: '' })).toBe('Bash')
    expect(labelFor('bash', {})).toBe('Bash')
    expect(labelFor('bash', { command: 'echo \x1b[31mred' })).not.toContain('\x1b')
  })

  test('mcp: server.tool', () => {
    expect(labelFor('mcp', { tool: 'mcp__github__search_code' })).toBe('github.search_code')
    expect(labelFor('mcp', { tool: 'mcp__srv__a__b' })).toBe('srv.a__b')
    expect(labelFor('mcp', { tool: 'mcp__only' })).toBe('only')
    expect(labelFor('mcp', {})).toBe('mcp')
  })

  test('subagent: type and description', () => {
    expect(labelFor('subagent', { subagentType: 'Explore', description: 'scan the repo' })).toBe('Explore: scan the repo')
    expect(labelFor('subagent', { subagentType: 'Explore' })).toBe('Explore')
    expect(labelFor('subagent', { description: 'scan' })).toBe('agent: scan')
    expect(labelFor('subagent', {})).toBe('agent')
    expect(labelFor('subagent', { subagentType: 'Explore', description: 'a\nb\x1b[0m' })).toBe('Explore: a b\\x1b[0m')
  })
})

describe('limitFor', () => {
  test('a Bash timeout in milliseconds is a limit', () => {
    expect(limitFor('bash', { timeout: 600_000 }, DEFAULTS)).toEqual({ limitMs: 600_000, limitKind: 'limit' })
  })

  test('a Bash call with no usable timeout uses the setting, or shows none', () => {
    expect(limitFor('bash', {}, DEFAULTS)).toEqual({ limitMs: null, limitKind: null })
    expect(limitFor('bash', { timeout: 0 }, DEFAULTS)).toEqual({ limitMs: null, limitKind: null })
    expect(limitFor('bash', { timeout: -5 }, DEFAULTS)).toEqual({ limitMs: null, limitKind: null })
    expect(limitFor('bash', { timeout: '60' }, DEFAULTS)).toEqual({ limitMs: null, limitKind: null })
    expect(limitFor('bash', { timeout: NaN }, DEFAULTS)).toEqual({ limitMs: null, limitKind: null })
    expect(limitFor('bash', {}, { ...DEFAULTS, bashDefaultLimitSeconds: 120 })).toEqual({ limitMs: 120_000, limitKind: 'limit' })
  })

  test('subagents and MCP calls get the advisory warn time', () => {
    expect(limitFor('subagent', {}, DEFAULTS)).toEqual({ limitMs: 600_000, limitKind: 'warn' })
    expect(limitFor('mcp', {}, DEFAULTS)).toEqual({ limitMs: 120_000, limitKind: 'warn' })
    expect(limitFor('mcp', { timeout: 5000 }, { ...DEFAULTS, mcpWarnSeconds: 30 })).toEqual({ limitMs: 30_000, limitKind: 'warn' })
  })
})

describe('list helpers', () => {
  test('addItem replaces an item with the same id and keeps order otherwise', () => {
    const one = addItem([], item({ id: 'a' }))
    const two = addItem(one, item({ id: 'b' }))
    expect(two.map(i => i.id)).toEqual(['a', 'b'])
    expect(addItem(two, item({ id: 'a', label: 'again' })).map(i => i.label)).toEqual(['again', 'pytest'])
  })

  test('removeItem drops by id and leaves the rest', () => {
    expect(removeItem([item({ id: 'a' }), item({ id: 'b' })], 'a').map(i => i.id)).toEqual(['b'])
    expect(removeItem([item({ id: 'a' })], 'zzz').length).toBe(1)
  })

  test('endAgent drops a subagent item by agent id only', () => {
    const items = [
      item({ id: 'agent:1', kind: 'subagent', agentId: '1' }),
      item({ id: 'x', kind: 'bash', agentId: '1' }),
      item({ id: 'agent:2', kind: 'subagent', agentId: '2' }),
    ]
    expect(endAgent(items, '1').map(i => i.id)).toEqual(['x', 'agent:2'])
  })

  test('setDoing and clearDoing touch only that subagent, and clear only the matching call', () => {
    const items = [item({ id: 'agent:1', kind: 'subagent', agentId: '1' }), item({ id: 'agent:2', kind: 'subagent', agentId: '2' })]
    const doing = { id: 'call-1', label: 'pytest', startedAt: 5 }
    const set = setDoing(items, '1', doing)
    expect(set[0].doing).toEqual(doing)
    expect(set[1].doing).toBeUndefined()
    expect(clearDoing(set, '1', 'other-call')[0].doing).toEqual(doing)
    expect(clearDoing(set, '1', 'call-1')[0].doing).toBeUndefined()
    expect(setDoing(items, 'missing', doing)).toEqual(items)
  })
})

describe('visibleRows', () => {
  const options = { ...DEFAULTS, minSeconds: 5, maxRows: 2 }

  test('an item shows at exactly minSeconds and not before', () => {
    const items = [item({ startedAt: 0 })]
    expect(visibleRows(items, 4_999, options).rows).toEqual([])
    expect(visibleRows(items, 5_000, options).rows.length).toBe(1)
  })

  test('longest first, capped, with the count of the rest', () => {
    const items = [
      item({ id: 'a', startedAt: 90_000 }),
      item({ id: 'b', startedAt: 10_000 }),
      item({ id: 'c', startedAt: 50_000 }),
      item({ id: 'd', startedAt: 99_000 }),
    ]
    const { rows, more } = visibleRows(items, 100_000, options)
    expect(rows.map(r => r.id)).toEqual(['b', 'c'])
    expect(more).toBe(1) // d (1s) is too young; a (10s) is the third qualifying row
  })

  test('ties keep a stable order and an empty list is empty', () => {
    const items = [item({ id: 'b', startedAt: 0 }), item({ id: 'a', startedAt: 0 })]
    expect(visibleRows(items, 10_000, DEFAULTS).rows.map(r => r.id)).toEqual(['a', 'b'])
    expect(visibleRows([], 10_000, DEFAULTS)).toEqual({ rows: [], more: 0 })
  })

  test('OVER is true at exactly the limit and not one millisecond before', () => {
    const items = [item({ startedAt: 0, limitMs: 10_000, limitKind: 'limit' })]
    expect(visibleRows(items, 9_999, DEFAULTS).rows[0].over).toBe(false)
    expect(visibleRows(items, 10_000, DEFAULTS).rows[0].over).toBe(true)
  })

  test('a row with no limit is never over, and elapsed is never negative', () => {
    expect(visibleRows([item({ startedAt: 0 })], 3_600_000, DEFAULTS).rows[0].over).toBe(false)
    expect(visibleRows([item({ startedAt: 50_000 })], 10_000, DEFAULTS).rows).toEqual([])
  })
})

describe('formatRows', () => {
  const NOW = 1_000_000
  const rows = (specs: Partial<Item>[]) => visibleRows(specs.map((s, i) => item({ id: String(i), ...s })), NOW, { ...DEFAULTS, maxRows: 10 }).rows

  test('kind, label, elapsed, and limit or warn', () => {
    const lines = formatRows(
      rows([
        { kind: 'bash', label: 'pytest -q tests/', startedAt: NOW - 130_000, limitMs: 600_000, limitKind: 'limit' },
        { kind: 'subagent', label: 'Explore: scan the repo', startedAt: NOW - 222_000, limitMs: 600_000, limitKind: 'warn' },
        { kind: 'mcp', label: 'github.search_code', startedAt: NOW - 65_000 },
      ]),
      0,
      NOW,
      100,
    )
    expect(lines[0]).toMatch(/^subagent {1}Explore: scan the repo {2,}3m42s \/ 10m00s warn$/)
    expect(lines[1]).toMatch(/^Bash {5}pytest -q tests\/ {2,}2m10s \/ 10m00s limit$/)
    expect(lines[2]).toMatch(/^mcp {6}github\.search_code {2,}1m05s$/)
  })

  test('an over row says OVER, and +N more closes the list', () => {
    const lines = formatRows(rows([{ label: 'sleep 400', startedAt: NOW - 602_000, limitMs: 600_000, limitKind: 'limit' }]), 3, NOW, 100)
    expect(lines[0].endsWith('10m02s / 10m00s limit  OVER')).toBe(true)
    expect(lines[1]).toBe('+3 more')
  })

  test('a subagent row ends with what it is doing now', () => {
    const lines = formatRows(
      rows([{ kind: 'subagent', label: 'Explore: scan', agentId: '1', startedAt: NOW - 60_000, doing: { id: 'c', label: 'pytest', startedAt: NOW - 12_000 } }]),
      0,
      NOW,
      100,
    )
    expect(lines[0]).toContain('Explore: scan → pytest 12s')
  })

  test('a narrow width shortens the label, never the times', () => {
    const lines = formatRows(
      rows([{ label: 'a very long command line that will not fit anywhere', startedAt: NOW - 130_000, limitMs: 600_000, limitKind: 'limit' }]),
      0,
      NOW,
      45,
    )
    expect(lines[0].endsWith('2m10s / 10m00s limit')).toBe(true)
    expect(Array.from(lines[0]).length).toBeLessThanOrEqual(45)
    expect(lines[0]).toContain('…')
    expect(formatRows(rows([{ label: 'x', startedAt: NOW - 10_000 }]), 0, NOW, 5)[0]).toContain('10s')
  })

  test('labels are aligned across rows', () => {
    const lines = formatRows(rows([{ label: 'short', startedAt: NOW - 20_000 }, { label: 'a longer label', startedAt: NOW - 10_000 }]), 0, NOW, 100)
    expect(lines[0].indexOf('20s')).toBe(lines[1].indexOf('10s'))
  })

  test('no rows and no more is no lines', () => {
    expect(formatRows([], 0, NOW, 100)).toEqual([])
  })
})
