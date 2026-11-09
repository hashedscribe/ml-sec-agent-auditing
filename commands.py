import json, re, shlex
from collections import Counter
from statistics import median

PATH = "samples/sample_v2.0_claudecode.jsonl"
THRESH = 0.90

# splits commands that are joint with &&, ||, etc.
SEPS = re.compile(r"&&|\|\||[;|]")
# << 'EOF', <<EOF etc
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
# env variables being declared 
ENV = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

PREFIX = {"sudo", "env", "nohup", "time", "exec", "command", "xargs"}


def bash_commands(row):
    out = []
    # have to pull from messages but Bash enabled in tools implies that Claude has full access
    for m in row["messages"]:
        for c in m.get("tool_calls") or []:
            name = c.get("name") or c.get("function", {}).get("name")
            # only pulling bash tools
            if name != "Bash":
                continue
            
            # pulls tool name from list and cleans up
            args = c.get("input") or c.get("arguments") or c.get("function", {}).get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    continue
            if isinstance(args, dict) and args.get("command"):
                out.append(args["command"])
    return out

def segments(cmd):
    # checks if there is a HEREDOC marker, if so, ignore the rest of the file
    # suspect if the LLM tries to sneak in commnds into file and then run the file that it wrote
    m = HEREDOC.search(cmd)
    if m:
        cmd = cmd[:m.start()]
    
    # strips seperators
    for part in SEPS.split(cmd):
        part = part.strip().lstrip("(").strip()
        if part and "\n" not in part:
            yield part

def heads(cmd):
    m = HEREDOC.search(cmd)
    if m:
        cmd = cmd[:m.start()]
    for seg in SEPS.split(cmd):
        if "\n" in seg:
            continue
        parts = seg.split()
        while parts and ("=" in parts[0] or parts[0] in PREFIX):
            parts = parts[1:]
        if parts and parts[0] == "timeout":
            parts = parts[2:]
        if parts:
            h = parts[0].strip("()[]{}'\"`")
            if h:
                yield h

def get_command_count(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    print(f"{len(rows)} rows")

    # faster than plain dict for large datasets
    counts = Counter()
    per_row = []

    for row in rows:
        seen = set()
        for cmd in bash_commands(row):
            for h in heads(cmd):
                counts[h] += 1
                seen.add(h)
        if seen:
            per_row.append(len(seen))
    return (counts, per_row)

counts, per_row = get_command_count(PATH)

# --------------------------- prelim summary stats --------------------------- #

total = sum(counts.values())
print(f"{total} commands, {len(counts)} distinct heads\n")

# get the 30 most common commands snad their 
for h, n in counts.most_common(30):
    print(f"{h:28} {n:7}  ({n/total:.1%})")

run = 0
for i, (_, n) in enumerate(counts.most_common(), 1):
    run += n
    if run / total >= THRESH:
        print(f"\n{i} heads cover {THRESH * 100}%")
        break

print(f"median distinct heads per session: {median(per_row):.0f} of {len(counts)}")