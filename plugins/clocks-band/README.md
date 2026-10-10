# clocks-band: a Claude Code mod by Naren

> A band above the prompt showing every Bash command, MCP call and subagent that has run for a while, with elapsed time against its limit.

Part of [Naren's Claude Toolkit](https://github.com/NarenDawar/narens-claude-toolkit).

## What it shows

Once something has run for 5 seconds (you can change that), it gets a row in a band above the prompt. The row goes away when the call ends. With nothing long-running, the band is not there at all.

```text
subagent  Explore: scan the repo      3m42s / 10m00s warn
Bash      pytest -q tests/            2m10s / 10m00s limit
mcp       github.search_code          1m05s
Bash      sleep 400                   10m02s / 10m00s limit  OVER
```

- **kind and label:** `Bash` with the command, `mcp` with the server and tool, `subagent` with its type and description. A subagent row can end with its latest tool call: `Explore: scan → pytest 12s`.
- **elapsed:** how long the mod has seen it running.
- **`limit`** is a time the engine states: a Bash call's own `timeout`. **`warn`** is an advisory time you set for subagents and MCP calls; the mod stops nothing at that time, it only marks the row `OVER`.
- Up to 4 rows (longest first) and then `+N more`.

## Settings

All optional; set them in `/config`.

| Setting | Default | Meaning |
| --- | --- | --- |
| Show after (seconds) | 5 | a row appears once the call has run this long |
| Most rows | 4 | rows before `+N more` |
| Subagent warn time (minutes) | 10 | a subagent row is marked `OVER` past this |
| MCP call warn time (seconds) | 120 | an MCP row is marked `OVER` past this |
| Limit shown for a Bash call with no timeout (seconds) | 0 | 0 shows no limit for a Bash call that has none of its own |

## What it does not do

Version 1 only watches. It cannot stop a command, a subagent or an MCP call, and it has no kill key and no enforced limits. Those need facts about what a mod is allowed to stop; a short live probe is planned first, then a separate v1.1. The band never changes, delays or blocks a call, and a failure inside it never reaches a call.

## Limits

- Elapsed time starts when the mod sees the call start; time before that is not counted, and calls shorter than the "show after" time never appear.
- Only a Bash call that carries a `timeout` shows an engine `limit`. Everything else shows an advisory `warn` time, or none.
- A Bash command started in the background is not shown (it returns at once).
- If the mod reloads while something runs, those rows are forgotten.
- Not checked live yet: how the band looks on your screen, and the subagent rows.

## Try it

This is a mod, so it loads from a folder rather than from the skills directory:

```text
claude --plugin-dir plugins/clocks-band
```

Then ask Claude to run something slow (for example `sleep 30`), and look above the prompt. Tests for the mod run with `claude plugin test plugins/clocks-band`.
