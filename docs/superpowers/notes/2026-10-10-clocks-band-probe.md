# clocks-band live probe: what can a hook stop?

Date: 2026-10-10. Real `claude -p` runs (Windows, build 2.1.296 per the earlier live check) with a throwaway mod (kept outside the repo) that logs to `probe.log`. Each run had `--max-budget-usd 0.30`, a fresh empty folder, and used `--permission-mode dontAsk` with only the tools named. Total cost about $0.36 (four runs: $0.14, $0.07, $0.07, $0.07). One run per experiment, so these are single observations, not statistics.

## 1. Basics

Prompt: run `echo hello`, then spawn one subagent that lists the folder.

- `tool.call` for Bash fired at the start and again when `next(e)` returned (about 5 s later), with `tool_use_id` set, `agent` unset, `timeout` undefined (the model gave none) and `run_in_background` undefined.
- `agent.spawn` fired for the model-started subagent and `next(e)` resolved to `{"model":"claude-sonnet-5-5","agentId":"a1650d5a47852f7c6"}`.
- `turn.complete` fired with that `agentId` when the subagent finished.
- `$.tool.list()` named 28 tools including `Bash`, `Agent`, `PowerShell`, `TaskStop`, `ListAgents`, `SendMessage`, `Monitor`, plus connected MCP tools as `mcp__<server>__<tool>`.
- Conclusion: the events clocks-band v1 relies on behave as assumed. A Bash call without an explicit `timeout` has the field undefined.

## 2. Abandon-race (a hook answers before `next(e)` settles)

Prompt: run `sleep 15 && touch marker.txt`. The probe raced `next(e)` against 3 s and answered `{ deny }`.

- The model saw the denial text as the tool's error.
- `marker.txt` did **not** appear, checked right after and 22 s later. The command was not left running to completion.
- Caveat: `claude -p` exited soon after, which could also end a child. Experiment 3 shows a Bash process survived `claude -p` exiting there (the marker appeared), which makes "the exit killed it" unlikely here, but this is one run.
- Conclusion: a hook that settles first appears to stop the Bash process beneath it. v1.1 can build a per-call time limit on this, to be re-checked with a repeat run before relying on it.

## 3. `$.turn.abort` from a timer

Prompt: the same `sleep 15` command; `$.turn.abort({ turnId })` called from `$.clock.after`.

- `$.turn.abort` returned normally.
- It did **not** kill the command. The engine moved the Bash call to the background: its result carried `backgroundTaskId` and `backgroundedByTurnAbort: true`, and `marker.txt` appeared 15 s later, after `claude -p` had already exited.
- Conclusion: `$.turn.abort` is not a way to stop a running Bash call, and it leaves a background task running. It also shows that a background shell can outlive `claude -p`.

## 4. Stop-task: `TaskStop` through `$.tool.call`

Prompt: run `sleep 40 && touch marker.txt` with `run_in_background: true`. After `next(e)`, the probe read `backgroundTaskId` from the result and called `$.tool.call({ tool: 'TaskStop', task_id })`.

- The call returned `Successfully stopped task: bxnm4zn5b (sleep 40 && touch marker.txt)` with `task_type: local_bash`.
- `marker.txt` did not appear 45 s later.
- Conclusion: a plugin can stop a background shell it started or sees, by calling the built-in `TaskStop` tool. **Not tested:** `TaskStop` on a running subagent (the tool's description says teammates and named background agents are accepted by ID or name), on a foreground Bash call, and on an MCP call.

## What v1.1 can build on

Shown by these runs:

- Per-call limits for Bash: a `tool.call` hook that races `next(e)` against a deadline and answers `{ deny }` appeared to stop the process (experiment 2, one run).
- Stopping background shells: `$.tool.call({ tool: 'TaskStop', task_id })` works (experiment 4).
- Display data: start and end events, `agentId` on spawn and `turn.complete`, and the tool list are available (experiment 1).

Not shown, so not to be assumed:

- A kill key for a foreground Bash call or an MCP call (no tested way besides the deadline race inside the hook).
- Stopping a running subagent (`TaskStop` on an agent ID is untested; `$.turn.abort` is whole-turn and only backgrounded the Bash call).
- That the deadline race also stops MCP calls, or works on every surface.
- Whether a `Button`/hotkey can trigger any of this (not probed).
