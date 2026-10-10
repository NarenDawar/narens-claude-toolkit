# clocks-band: a band of what is running and for how long

Date: 2026-10-10

## Purpose

When a Bash command, an MCP call or a subagent runs for minutes, Claude Code shows little about how long it has been running or whether it is stuck. This mod adds a band above the prompt that lists everything that has run for a while, with elapsed time and, where one exists, a limit to compare it with. Version 1 only watches: it never changes, delays or stops a call. Stopping things (per-task limits, a kill key) needs facts about the mods API that are not known yet, so it waits for a short live probe and a v1.1 designed from its findings.

## Success criteria

1. While a tool call or subagent has run for at least `minSeconds`, the band shows one row for it with its kind, label and elapsed time; the row disappears when it ends, throws or is abandoned; with nothing long-running the band shows nothing.
2. A Bash call that carries a `timeout` shows it as `limit`; subagents and MCP calls show a configurable advisory `warn` time; the two are worded differently, and a row at or over its time is marked `OVER`.
3. The mod never changes, delays or blocks a call or its result, and a failure inside the mod never reaches a call.
4. The tests pass with `claude plugin test`, `claude plugin validate` passes, and the repository validator, catalog and tests stay green.
5. The live probe is run and its findings are written down for v1.1.

## Decisions already made

- **Scope:** display first. Enforcement and the kill key are v1.1, designed after the probe.
- **What shows:** only items that have run `minSeconds` (default 5); up to `maxRows` rows (default 4) plus `+N more`; longest first; nothing when nothing qualifies.
- **Limits:** a Bash call's own `timeout` is a `limit`; subagent and MCP "warn after" times come from the plugin's settings and are shown as `warn`; the two are never worded alike.

## Constraints and assumptions

- A mod is TypeScript in the mod runtime (no Node, no DOM), imports only `claude-code`, and draws elements from `$.ui.resolve(e)`.
- Elapsed time is measured from the moment the mod sees a call start, with `Date.now()`; time before that is not counted. A call shorter than `minSeconds` never shows.
- Labels (commands, subagent descriptions, MCP tool names) are untrusted text: control characters are escaped and long values are cut.
- To be verified against the type file while writing the plan (each is a task step with a stated fallback): how a `tool.call` hook matches MCP tools (`mcp__*`) and the Agent tool; whether the call input carries `timeout` for Bash and under what name; the shape and matcher of the `agent.spawn` hook and what `turn.complete` carries for a subagent; how `userConfig` options are declared in the manifest and read in `register`; how `$.clock.interval` is cancelled and reloaded; how an `AbovePrompt` `ui.render` hook returns "nothing".
- Known unknown that the live probe settles for v1.1: whether a hook that settles before `next(e)` really stops the process beneath it; whether `$.turn.abort` stops a running Bash; which tool names exist for stopping a background task or subagent and whether `$.tool.call` can use them.

## What it watches

- **Tool calls:** a `tool.call` hook (Bash, tools named `mcp__*`, and the Agent tool's own call is covered by the subagent path below) adds an item when the call starts and removes it in a `finally` when `next(e)` returns, throws or is abandoned. It always returns what `next` returned, untouched.
- **Subagents:** an `agent.spawn` hook adds an item once the subagent has started (when its `next(e)` resolves with the `agentId`), labeled `<type>: <description>`; the item ends on that agent's `turn.complete` or when `$.agent.list()` no longer reports it `running`. A subagent's own tool calls carry its `agentId`, so its row can end with its latest tool call and how long that has run, cut short.
- **Item ids:** the call's `tool_use_id` when the event carries one, else a counter; parallel calls are separate items.
- **Redraw:** one `$.clock.interval` of one second, started when the first item is added and cancelled when the last is removed, writes a tick into session state so the band redraws; an idle session does no work.
- **Clearing:** `session.end` with reason `clear` or `resume` empties the list. If the mod reloads, running items are forgotten.
- **Failure:** every hook's own code is wrapped so an error is swallowed and the call proceeds as if the mod were not there.

## The band

A `ui.render` hook on `{ component: 'AbovePrompt' }` returns nothing when no item qualifies, otherwise rows like:

```text
Bash       pytest -q tests/                  2m10s / 10m limit
subagent   Explore: scan the repo            3m42s / 10m warn
mcp        github.search_code                1m05s
Bash       sleep 400                         10m02s / 10m limit  OVER
```

- Columns: kind tag, label, elapsed (`45s`, `2m10s`, `1h05m`), then `/ <time> limit` or `/ <time> warn` when a time exists, then `OVER` when elapsed is at or past it.
- `OVER` rows are also styled with a warning color where the surface supports it; the word alone carries the meaning where it does not.
- Rows are sorted by elapsed time, longest first; more than `maxRows` ends with `+N more`.
- On a narrow terminal the label is shortened first; the time and the limit text are never cut.

## Settings

Declared as `userConfig` options in `plugin.json`, all optional:

| Setting | Default | Meaning |
| --- | --- | --- |
| `minSeconds` | 5 | an item shows once it has run this long |
| `maxRows` | 4 | rows before `+N more` |
| `subagentWarnMinutes` | 10 | warn time for a subagent |
| `mcpWarnSeconds` | 120 | warn time for an MCP call |
| `bashDefaultLimitSeconds` | 0 | the limit shown for a Bash call with no `timeout`; 0 means none is shown |

Out-of-range or non-numeric values fall back to the default.

## Structure

New plugin `plugins/clocks-band/` (name `clocks-band`, version 0.1.0, MIT, author Naren, as for the other mods):

- `.claude-plugin/plugin.json` with the `userConfig` options and `types`.
- `hooks/hooks.json`: `{ "modules": ["./register.ts"] }`.
- `hooks/clocks.ts` (pure): `Item`, `addItem`, `removeItem`, `visibleRows(items, now, options)`, `formatDuration(ms)`, `formatRow(row, width)`, `limitFor(kind, input, options)`, `labelFor(kind, input)`, `escapeText`. Takes `now` as an argument, so tests control time.
- `hooks/register.ts`: the hooks, the interval and the band; the only file that touches `$`.
- `types/index.d.ts`: the session-state contract (`{ items: Item[], tick: number }`).
- `hooks/*.test.ts` and a `README.md`.

## Testing

Written first, with `claude plugin test`; nothing calls a real model.

- **Pure module:** `formatDuration` at 0, 59, 60, 125, 3600 and 3725 seconds; `visibleRows` at the `minSeconds` boundary (4.9 and 5.0 seconds), ordering, the cap and the `+N more` count, zero rows; `limitFor` (Bash with and without `timeout`, with `bashDefaultLimitSeconds`, subagent and MCP warn times, bad settings falling back); the `OVER` rule at exactly the limit; labels cut and escaped (ANSI sequences, newlines, very long text, empty command).
- **Hooks, through the engine harness:** an item exists while a stubbed `tool.call` is pending and is gone after it returns, after it throws and when abandoned; two parallel calls give two items; the result passes through unchanged; a throwing state write does not break the call; `agent.spawn` adds and `turn.complete` removes a subagent item; `session.end` with `clear` or `resume` empties the list; the interval is started only while an item exists.
- **Band:** drawn through the kit's `mount` on each surface the kit offers: empty with no long-running item; rows with the right text and `OVER`; `+N more`.
- A mutation check of the main behaviors (the `minSeconds` boundary, `finally` removal, pass-through, `OVER` at the limit, limit-versus-warn wording), then a fresh Opus review of the whole branch.

## The live probe (before v1.1, not shipped)

A throwaway mod kept outside the plugin folders, run with `claude -p --plugin-dir` under a small budget cap, each run approved by the owner first, answering: (1) does a hook that answers before `next(e)` settles stop the process beneath it (`sleep 15 && touch marker` and look for the marker); (2) does `$.turn.abort` stop a running Bash; (3) the real tool names from `$.tool.list()` and whether a stop-task tool called through `$.tool.call` stops a background shell or subagent; (4) the basics v1 relies on (a `tool.call` hook sees start and end; an `agent.spawn` hook fires for a model-started subagent; the name and unit of a Bash call's `timeout`). Findings go into `docs/superpowers/notes/2026-10-10-clocks-band-probe.md`; v1.1 gets its own spec.

## Repo integration

A marketplace entry; the generated README catalog and `llms.txt` (`scripts/build_catalog.py`); `scripts/validate.py` and `claude plugin validate plugins/clocks-band` green; a `CHANGELOG.md` entry; a README with a keyword-rich H1, what it shows, the settings, an example band, and the honest limits below. Mod tests run locally with `claude plugin test`; the repository CI does not run them.

## Honest limits (for the README)

- Version 1 only watches. It cannot stop or limit anything.
- Elapsed time starts when the mod sees the call start; calls shorter than `minSeconds` never show.
- Only a Bash call with an explicit `timeout` shows an engine limit; everything else is an advisory `warn` time you set.
- Running items are forgotten if the mod reloads.
- Not checked live: how the band looks, and the subagent rows.

## Out of scope

Killing or limiting anything, the kill key, per-agent-type and per-tool warn tables, notifications or sounds, a history log, a Timeout Detective skill, and publishing.
