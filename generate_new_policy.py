import json, re
from commands import *

RULE = re.compile(r"^Bash\((.+?)(?::\*|\s*\*)?\)$")

SUB = {
    "git": {
        "read":   ["status", "diff", "log", "show", "blame", "ls-files",
                   "rev-parse", "describe", "cat-file", "branch", "remote"],
        "write":  ["add", "commit", "checkout", "stash", "apply", "restore",
                   "reset", "clean", "merge", "rebase", "cherry-pick", "mv", "rm"],
        "danger": ["push", "config", "filter-branch", "gc", "reflog"],
    },
    "pip": {
        "read":   ["show", "list", "freeze", "check"],
        "write":  ["install", "uninstall", "download"],
        "danger": [],
    },
}

POLICY_IN = ".claude/settings.json"
POLICY_OUT = "output/settings.suggested.json"


def subcommand_rules(rows, head, spec, min_calls=1):
    """-> (allow, ask, deny) lists of 'head sub' strings."""
    prof = subcommand_profile(rows, head)
    allow, ask, deny = [], [], []
    for tier, subs in spec.items():
        for s in subs:
            n = prof.get(s, 0)
            if n < min_calls:
                deny.append(f"{head} {s}")
            elif tier == "read":
                allow.append(f"{head} {s}")
            else:
                ask.append(f"{head} {s}")
    return allow, ask, deny


def rule_command(rule):
    """'Bash(git:*)' -> 'git'. Returns None for non-Bash or unparseable rules."""
    m = RULE.match(rule.strip())
    if not m:
        return None
    return m.group(1).split()[0] if m.group(1).split() else None


def load_policy(path):
    """Read an existing settings.json. Returns ({tier: [raw rules]}, full doc)."""
    try:
        doc = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        doc = {}
    perms = doc.get("permissions", {})
    tiers = {t: list(perms.get(t, [])) for t in ("deny", "ask", "allow")}
    return tiers, doc


def build_policy(counts, risk, rows=None, top_n=25, existing=None):
    known = {c: cat for cat, cmds in risk.items() for c in cmds}
    observed = {h for h, n in counts.items() if n > 0 and h in known}

    # commands already governed by the current policy, at any tier
    covered = set()
    if existing:
        for rules in existing.values():
            for r in rules:
                c = rule_command(r)
                if c:
                    covered.add(c)

    deny_cats = {"network", "install", "privilege", "destructive", "shell_meta"}

    deny_cmds = sorted(
        c for c, cat in known.items()
        if cat in deny_cats and c not in observed and c not in covered
    )
    ask_cmds = sorted(
        c for c, cat in known.items()
        if cat in deny_cats and c in observed and c not in covered
    )
    allow_cmds = [
        h for h, _ in counts.most_common()
        if h in known and h not in covered
        and known[h] not in deny_cats
    ][:top_n]
    
    
    if rows:
        for head, spec in SUB.items():
            if counts.get(head, 0) == 0 or head in covered:
                continue
            a, k, d = subcommand_rules(rows, head, spec)
            allow_cmds += a
            ask_cmds += k
            deny_cmds += d
            # drop the bare head so it doesn't re-grant everything
            ask_cmds = [c for c in ask_cmds if c != head]
            allow_cmds = [c for c in allow_cmds if c != head]
            # anything not enumerated still prompts
            ask_cmds.append(f"{head}")

    return allow_cmds, deny_cmds, ask_cmds


def merge_policy(doc, allow, deny, ask):
    """Append new rules to an existing settings doc without disturbing it."""
    out = json.loads(json.dumps(doc)) if doc else {
        "$schema": "https://json.schemastore.org/claude-code-settings.json"
    }
    perms = out.setdefault("permissions", {})
    for tier, cmds in (("deny", deny), ("ask", ask), ("allow", allow)):
        have = perms.setdefault(tier, [])
        for c in cmds:
            rule = f"Bash({c}:*)"
            if rule not in have:
                have.append(rule)
    perms.setdefault("defaultMode", "ask")
    return out

def main():
    counts, per_row, rows = get_command_count(PATH)

    total = sum(counts.values())
    print(f"{len(rows)} sessions, {total} commands, {len(counts)} distinct heads")
    print(f"median distinct heads per session: {median(per_row):.0f}\n")

    unknown = non_sorted_commands(counts, RISK)
    junk = sum(1 for n in unknown.values() if n <= 2)
    print(f"unclassified: {len(unknown)} heads, {junk} appearing <=2 times "
          f"({sum(unknown.values())} calls, {sum(unknown.values())/total:.1%})\n")

    tiers, doc = load_policy(POLICY_IN)
    allow, deny, ask = build_policy(counts, RISK, rows=rows, existing=tiers)

    print(f"deny  ({len(deny)}): {', '.join(deny)}\n")
    print(f"ask   ({len(ask)}): {', '.join(ask)}\n")
    print(f"allow ({len(allow)}): {', '.join(allow)}\n")

    merged = merge_policy(doc, allow, deny, ask)
    with open(POLICY_OUT, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    print(f"wrote {POLICY_OUT}")


if __name__ == "__main__":
    main()