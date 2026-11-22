# stuck-loop-detector

A Claude Code mod that notices when Claude is going in circles. It watches tool calls and flags two patterns: the same call (same tool, same arguments) three times in a row, and a strict A,B,A,B,A,B bounce between two calls.

When it fires it shows `loop? Bash x3` in the status line, pops a toast, and adds a note after the tool result telling Claude to stop, say what it expected, and change approach or ask you. It never blocks a call.

An Edit, MultiEdit, Write or NotebookEdit clears the history, so re-running tests after a change is not flagged. History is kept per agent and cleared when you send a prompt.

Limits: it only sees exact repeats, so a loop with slightly varied arguments is missed. Polling the same command on purpose will be flagged; ignore the note.
