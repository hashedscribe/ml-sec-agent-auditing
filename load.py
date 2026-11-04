import json

def declared(row):
    out = set()
    for t in row["tools"]:
        t = json.loads(t) if isinstance(t, str) else t
        out.add(t.get("name") or t["function"]["name"])
    return out

def used(row):
    out = set()
    for m in row["messages"]:
        for c in m.get("tool_calls") or []:
            out.add(c.get("name") or c["function"]["name"])
    return out

import shlex

def commands(row):
    out = []
    for m in row["messages"]:
        for c in m.get("tool_calls") or []:
            name = c.get("name") or c["function"]["name"]
            if name != "Bash":
                continue
            args = c.get("input") or c.get("arguments") or c["function"]["arguments"]
            if isinstance(args, str):
                args = json.loads(args)
            cmd = args.get("command", "")
            if cmd:
                out.append(cmd)
    return out