"""Prompts and reply parsing for the benchmark. Pure; standard library only."""
import json
import re

MAX_REPLY_CHARS = 20000


def _oneline(value):
    return " ".join(value.split()) if isinstance(value, str) else ""


def _is_tool(tool):
    return isinstance(tool, dict) and isinstance(tool.get("name"), str) and bool(tool["name"])


def render_tools(tools):
    """Each tool as a name and description line, then one line per parameter."""
    lines = []
    for tool in tools:
        if not _is_tool(tool):
            continue
        description = _oneline(tool.get("description"))
        lines.append(f"- {tool['name']}: {description}" if description else f"- {tool['name']}")
        schema = tool.get("inputSchema")
        props = schema.get("properties") if isinstance(schema, dict) else None
        if not isinstance(props, dict):
            continue
        required = schema.get("required")
        required = {r for r in required if isinstance(r, str)} if isinstance(required, list) else set()
        for pname, prop in props.items():
            prop = prop if isinstance(prop, dict) else {}
            bits = []
            kind = prop.get("type")
            if isinstance(kind, str):
                bits.append(kind)
            elif isinstance(kind, list):
                bits.append("|".join(str(k) for k in kind))
            if pname in required:
                bits.append("required")
            values = prop.get("enum")
            if isinstance(values, list) and values:
                bits.append("one of " + ", ".join(str(v) for v in values))
            head = f"    - {pname}" + (f" ({'; '.join(bits)})" if bits else "")
            text = _oneline(prop.get("description"))
            lines.append(f"{head}: {text}" if text else head)
    return "\n".join(lines)


def trial_prompt(tools, request):
    return (
        "You are choosing a tool for a user request. These are the available tools:\n\n"
        + render_tools(tools)
        + "\n\nUser request: "
        + request
        + "\n\nChoose the single best tool for this request. Reply with exactly one JSON object "
        'and nothing else, in the form {"tool": "<tool name>"}.'
    )


def tasks_prompt(tools, target, per_tool):
    return (
        "These are the tools of an MCP server:\n\n"
        + render_tools(tools)
        + f"\n\nWrite {per_tool} different requests that a person might type to an assistant when they "
        f'need the tool "{target}" and not any other tool above. Write each one as the person would say it, '
        "in plain words about their goal. Do not mention the tool's name and do not copy phrases from its "
        f"description. Reply with exactly one JSON array of {per_tool} strings and nothing else."
    )


def _json_values(text):
    """Every top-level JSON object or array found in `text`, in order."""
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        if text[index] in "{[":
            try:
                value, end = decoder.raw_decode(text, index)
            except (ValueError, RecursionError):
                index += 1
                continue
            yield value
            index = end
        else:
            index += 1


def parse_choice(text, names):
    """The tool name a reply picked, or None when the reply is unusable.

    The last JSON object with a string "tool" decides; its value must be exactly one of `names`.
    Earlier objects may be quoted from a tool description rather than the model's final answer.
    """
    choice = None
    for value in _json_values(text[:MAX_REPLY_CHARS]):
        if isinstance(value, dict) and isinstance(value.get("tool"), str):
            choice = value["tool"]
    return choice if choice in names else None


def parse_task_list(text):
    """The strings of the first JSON array in a reply (empty ones dropped), or None."""
    for value in _json_values(text[:MAX_REPLY_CHARS]):
        if isinstance(value, list):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return None


def mentions_name(request, name):
    """True when `request` contains the tool's name (or the name with _ or - as spaces) as a word."""
    variants = {name, re.sub(r"[_-]", " ", name)}
    for variant in variants:
        if variant and re.search(
            r"(?<![A-Za-z0-9])" + re.escape(variant) + r"(?![A-Za-z0-9])", request, re.IGNORECASE
        ):
            return True
    return False
