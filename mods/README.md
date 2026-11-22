# Mods

Claude Code mods (plugin-authoring hooks modules), kept apart from the skills in `plugins/`.

- `stuck-loop-detector`: flags repeated or bouncing tool calls and tells Claude to change approach.
- `outgoing-secret-guard`: redacts secrets in prompts and tool output, and blocks network-bound calls that carry one.

Try one with `claude --plugin-dir mods/<name>`; test with `claude plugin test mods/<name>`.
