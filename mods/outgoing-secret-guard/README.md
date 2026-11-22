# outgoing-secret-guard

A Claude Code mod that keeps secrets from leaving your machine. When you send a prompt, it replaces API keys, tokens, JWTs, private-key blocks and `password = ...` style values with `[REDACTED:kind]` before the model sees it, and shows a toast naming what it caught. It also denies WebFetch, WebSearch, MCP and network-shell calls (curl, wget, ssh, scp and similar) whose arguments contain a secret, telling Claude to read it from the environment instead.

What tools bring back (file contents, command output, MCP results) is masked the same way before the model reads it, so a key in `.env` or in a log never reaches it.

If the scanner itself throws, the prompt is dropped and the call is denied rather than let through.

Limits: pattern matching only, so unusual formats and obfuscated keys get through, and the generic rule can miss or over-match. It cannot see what a script or subprocess sends on its own. A masked file shows a placeholder, so an Edit whose old text includes a secret will not match the real file. Secrets written by Claude into local files are not blocked.
