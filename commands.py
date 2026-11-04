import json, re, shlex
from collections import Counter
from statistics import median

PATH = "samples/sample_v2.0_claudecode.jsonl"

SEPS = re.compile(r"&&|\|\||[;|]")
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
ENV = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
PREFIX = {"sudo", "env", "nohup", "time", "exec", "command", "xargs"}


def bash_commands(row):
    out = []
    for m in row["messages"]:
        for c in m.get("tool_calls") or []:
            name = c.get("name") or c.get("function", {}).get("name")
            if name != "Bash":
                continue
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
    m = HEREDOC.search(cmd)
    if m:
        cmd = cmd[:m.start()]
    for part in SEPS.split(cmd):
        part = part.strip().lstrip("(").strip()
        if part and "\n" not in part:
            yield part


def head(segment):
    try:
        parts = shlex.split(segment)
    except ValueError:
        return None
    while parts and (ENV.match(parts[0]) or parts[0] in PREFIX):
        parts = parts[1:]
    if parts and parts[0] == "timeout":
        parts = parts[2:] if len(parts) > 2 else []
    if not parts:
        return None
    h = parts[0].strip("()[]{}'\"")
    return h or None


rows = [json.loads(l) for l in open(PATH, encoding="utf-8")]
print(f"{len(rows)} rows")

sample = bash_commands(rows[0])
print(f"first row: {len(sample)} bash calls")
for c in sample[:3]:
    print("   ", c[:90].replace("\n", " "))
print()

heads = Counter()
per_row = []
unparsed = 0

for row in rows:
    seen = set()
    for cmd in bash_commands(row):
        for seg in segments(cmd):
            h = head(seg)
            if h is None:
                unparsed += 1
            else:
                heads[h] += 1
                seen.add(h)
    if seen:
        per_row.append(len(seen))

total = sum(heads.values())
print(f"{total} commands, {unparsed} unparsed, {len(heads)} distinct heads\n")

for h, n in heads.most_common(30):
    print(f"{h:28} {n:7}  ({n/total:.1%})")

run = 0
for i, (_, n) in enumerate(heads.most_common(), 1):
    run += n
    if run / total >= 0.95:
        print(f"\n{i} heads cover 95% of calls")
        break

print(f"median distinct heads per session: {median(per_row):.0f} of {len(heads)} permitted")