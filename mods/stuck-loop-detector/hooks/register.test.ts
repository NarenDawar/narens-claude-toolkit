import { expect, test } from 'claude-code/testing'

test('the third identical call gets a note for Claude; an edit resets', async ($, on) => {
  on('tool.call', () => ({ result: {} }))
  const call = (cmd: string) => $.tool.call({ tool: 'Bash', command: cmd })

  expect((await call('npm test')).context).toBeUndefined()
  expect((await call('npm test')).context).toBeUndefined()
  const third = await call('npm test')
  expect(third.deny).toBeUndefined()
  expect(third.context?.[0]).toMatch(/3 times in a row/)

  await $.tool.call({ tool: 'Edit', file_path: '/a', old_string: 'x', new_string: 'y' })
  expect((await call('npm test')).context).toBeUndefined()
})

test('different calls and a two-call bounce', async ($, on) => {
  on('tool.call', () => ({ result: {} }))
  const read = (p: string) => $.tool.call({ tool: 'Read', file_path: p })
  const out = []
  for (const p of ['a', 'b', 'c', 'a', 'b', 'c']) out.push(await read(p))
  expect(out.every(r => r.context === undefined)).toBe(true)

  const bounce = []
  for (const p of ['x', 'y', 'x', 'y', 'x', 'y']) bounce.push(await read(p))
  expect(bounce[5].context?.[0]).toMatch(/alternate/)
})
