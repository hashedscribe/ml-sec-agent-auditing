import json

def build_policy(counts, risk, top_n=25):
    known = {c: cat for cat, cmds in risk.items() for c in cmds}

    observed = {h for h, n in counts.items() if n > 0 and h in known}
    allow_cmds = [h for h, _ in counts.most_common() if h in known][:top_n]

    deny_cats = {"network", "install", "privilege", "destructive", "shell_meta"}
    deny_cmds = sorted(
        c for c, cat in known.items()
        if cat in deny_cats and c not in observed
    )

    ask_cmds = sorted(
        c for c, cat in known.items()
        if cat in deny_cats and c in observed
    )

    return allow_cmds, deny_cmds, ask_cmds


def claude_code(allow, deny, ask):
    return {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "permissions": {
            "deny": [f"Bash({c}:*)" for c in deny],
            "ask":  [f"Bash({c}:*)" for c in ask],
            "allow": [f"Bash({c}:*)" for c in allow],
            "defaultMode": "ask",
        },
    }