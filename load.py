import json

def declared(row):
    out = set()
    for t in row["tools"]:
        t = json.loads(t) if isinstance(t, str) else t
        out.add(t["function"]["name"])
    return out

def used(row):
    out = set()
    for m in row["messages"]:
        for c in m.get("tool_calls") or []:
            out.add(c["function"]["name"])
    return out