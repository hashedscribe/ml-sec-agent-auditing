"""Fetch samples from nvidia/Open-SWE-Traces without downloading the whole dataset.

Examples:
  python fetch_samples.py                      # first 1000 rows (same file commands.py reads)
  python fetch_samples.py -count 200           # first 200 rows
  python fetch_samples.py -count 200 -R        # ~random 200 rows (shuffle buffer, see below)
  python fetch_samples.py -repo owner/name     # first 1000 rows from one repo
  python fetch_samples.py -repo owner/name -A  # every row from one repo
  python fetch_samples.py -A                   # everything (asks for confirmation)
  python fetch_samples.py --list-repos         # one full pass, writes a per-repo CSV index

Notes:
  * Always streams (streaming=True), nothing is cached to disk by `datasets`.
  * -R on a stream is only approximately random: rows are shuffled inside a
    buffer (--buffer-size) and shard order is shuffled. A bigger buffer is more
    random but slower to start.
  * The repo field name is not known ahead of time. The script tries common
    names and instance_id ("owner__repo-123"). Override with --repo-field.
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter

from dotenv import load_dotenv
from datasets import load_dataset, load_dataset_builder

load_dotenv()

NAME = "nvidia/Open-SWE-Traces"
CONFIG = "v2.0"
SPLIT = "claudecode"
OUT_DIR = "samples"
DEFAULT_N = 1000
DEFAULT_BUFFER = 10_000
DEFAULT_PATH = os.path.join(OUT_DIR, f"sample_{CONFIG}_{SPLIT}.jsonl")
INDEX_PATH = os.path.join(OUT_DIR, f"repo_index_{CONFIG}_{SPLIT}.csv")

REPO_KEYS = ("repo", "repo_name", "repository", "repo_full_name", "github_repo")


# ------------------------------- helpers ------------------------------------ #
def get_path(row, dotted):
    cur = row
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def repo_of(row, field=None):
    """Best-effort repo name for a row, or None if it cannot be found."""
    if field:
        v = get_path(row, field)
        return v if isinstance(v, str) and v else None
    for src in (row, row.get("metadata") if isinstance(row.get("metadata"), dict) else {}):
        for k in REPO_KEYS:
            v = src.get(k)
            if isinstance(v, str) and v:
                return v
    iid = row.get("instance_id")
    if isinstance(iid, str) and "__" in iid:
        owner, rest = iid.split("__", 1)
        return f"{owner}/{rest.rsplit('-', 1)[0]}"
    return None


def open_stream():
    return load_dataset(NAME, CONFIG, split=SPLIT, streaming=True)


def total_rows():
    """Row count if the hub metadata has it, else None."""
    try:
        info = load_dataset_builder(NAME, CONFIG).info
        return info.splits[SPLIT].num_examples
    except Exception:
        return None


def confirm(msg, assume_yes):
    print(msg)
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print("Not an interactive terminal. Re-run with --yes to proceed.")
        return False
    return input("Continue? [y/N] ").strip().lower() in ("y", "yes")


def safe_tag(s):
    return "".join(c if c.isalnum() or c in "-._" else "-" for c in s)


# ------------------------------- commands ----------------------------------- #
def list_repos(args):
    n = total_rows()
    size = f"{n:,} rows" if n else "an unknown number of rows"
    if not confirm(f"--list-repos reads the entire split ({size}).", args.yes):
        return
    counts = Counter()
    missing = 0
    for row in open_stream():
        r = repo_of(row, args.repo_field)
        if r is None:
            missing += 1
        else:
            counts[r] += 1
    if not counts:
        print("Could not find a repo field on any row. Pass --repo-field.")
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(INDEX_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["repo", "rows"])
        for r, c in counts.most_common():
            w.writerow([r, c])
    print(f"{len(counts)} repos, {sum(counts.values())} rows indexed, {missing} rows without a repo")
    for r, c in counts.most_common(15):
        print(f"  {c:6d}  {r}")
    print(f"wrote {INDEX_PATH}")


def fetch(args):
    limit = None if args.all else (args.count or DEFAULT_N)

    if args.all:
        if args.repo:
            msg = f"-A with -repo will scan the whole split to find every row from {args.repo}."
        else:
            n = total_rows()
            msg = f"-A will download the entire split ({f'{n:,} rows' if n else 'size unknown'}). This can be very large."
        if not confirm(msg, args.yes):
            print("aborted")
            return

    ds = open_stream()
    if args.random:
        ds = ds.shuffle(seed=args.seed, buffer_size=args.buffer_size)

    wanted = args.repo.lower() if args.repo else None
    tag = []
    if args.repo:
        tag.append("repo-" + safe_tag(args.repo))
    if args.random:
        tag.append(f"rand{args.seed}")
    if args.all:
        tag.append("all")
    elif args.count and (tag or args.count != DEFAULT_N):
        tag.append(f"n{args.count}")
    path = args.out or (
        DEFAULT_PATH if not tag
        else os.path.join(OUT_DIR, f"sample_{CONFIG}_{SPLIT}_{'_'.join(tag)}.jsonl")
    )
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    written = 0
    checked_field = False
    with open(path, "w", encoding="utf-8") as f:
        for row in ds:
            if wanted:
                r = repo_of(row, args.repo_field)
                if r is None and not checked_field:
                    print("Could not find a repo field on the first row.")
                    print("Top-level keys:", ", ".join(row.keys()))
                    print("Re-run with --repo-field <key> (dotted paths work, e.g. metadata.repo).")
                    f.close()
                    os.remove(path)
                    return
                checked_field = True
                if r is None or r.lower() != wanted:
                    continue
            f.write(json.dumps(row) + "\n")
            written += 1
            if limit is not None and written >= limit:
                break

    if written == 0:
        print("No rows matched." + (" Try --list-repos to see exact repo names." if wanted else ""))
    else:
        print(f"wrote {written} rows to {path}")
        if limit is not None and wanted and written < limit:
            print(f"only {written} rows exist for {args.repo} (asked for {limit})")


# --------------------------------- cli ---------------------------------------- #
def parse():
    p = argparse.ArgumentParser(description="Fetch samples from Open-SWE-Traces (streaming).")
    p.add_argument("-count", "--count", type=int, help=f"number of samples (default {DEFAULT_N})")
    p.add_argument("-A", "--all", action="store_true", help="pull all rows (asks for confirmation)")
    p.add_argument("-repo", "--repo", help="only rows from this repo, e.g. owner/name")
    p.add_argument("-R", "--random", action="store_true", help="shuffle instead of taking the first N")
    p.add_argument("--seed", type=int, default=0, help="shuffle seed for -R (default 0)")
    p.add_argument("--buffer-size", type=int, default=DEFAULT_BUFFER, help="shuffle buffer for -R")
    p.add_argument("--repo-field", help="row key holding the repo name (dotted path ok)")
    p.add_argument("--list-repos", action="store_true", help="scan the split and write a repo index CSV")
    p.add_argument("--out", help="output path (default depends on options)")
    p.add_argument("--yes", action="store_true", help="skip confirmation prompts")
    args = p.parse_args()
    if args.all and args.count:
        p.error("-A and -count are mutually exclusive")
    if args.count is not None and args.count < 1:
        p.error("-count must be positive")
    return args


if __name__ == "__main__":
    a = parse()
    list_repos(a) if a.list_repos else fetch(a)
