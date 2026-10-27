"""Stdio MCP server: newline-delimited JSON-RPC, standard library only."""
import json
import os
import sys

from . import __version__
from .client import DEFAULT_URL, AnkiConnect, AnkiError
from .tools import TOOLS, ToolInputError

PROTOCOL_VERSION = "2025-06-18"
_HANDLERS = {name: handler for name, _, _, handler in TOOLS}


def _tool_list():
    return [
        {"name": name, "description": description, "inputSchema": schema}
        for name, description, schema, _ in TOOLS
    ]


def _call_tool(anki, params):
    name = params.get("name")
    if name not in _HANDLERS:
        raise KeyError(name)
    arguments = params.get("arguments") or {}
    try:
        text = json.dumps(_HANDLERS[name](anki, arguments), indent=2, ensure_ascii=False)
        return {"content": [{"type": "text", "text": text}]}
    except (AnkiError, ToolInputError) as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}


def handle(anki, message):
    """Return the JSON-RPC response for one request, or None for a notification."""
    method, request_id = message.get("method"), message.get("id")
    if request_id is None:
        return None
    try:
        if method == "initialize":
            result = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "anki-mcp", "version": __version__},
            }
        elif method == "tools/list":
            result = {"tools": _tool_list()}
        elif method == "tools/call":
            result = _call_tool(anki, message.get("params") or {})
        elif method == "ping":
            result = {}
        else:
            return {"jsonrpc": "2.0", "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}}
    except KeyError as exc:
        return {"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32602, "message": f"Unknown tool: {exc.args[0]}"}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def serve(anki, stdin=sys.stdin, stdout=sys.stdout):
    for line in stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None,
                     "error": {"code": -32700, "message": "Parse error"}}
        else:
            reply = handle(anki, message) if isinstance(message, dict) else None
        if reply is not None:
            stdout.write(json.dumps(reply) + "\n")
            stdout.flush()


def run():
    serve(AnkiConnect(os.environ.get("ANKI_CONNECT_URL", DEFAULT_URL)))
