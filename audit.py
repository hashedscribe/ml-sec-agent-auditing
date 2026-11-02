import json, os
from collections import Counter
from dotenv import load_dotenv
from datasets import load_dataset
from load import declared, used

load_dotenv()

NAME = "ArkhAngelLifeJiggy/Open-SWE-Traces"
PATH = "sample.jsonl"
N = 100

if not os.path.exists(PATH):
    ds = load_dataset(NAME, "v1.0", split="openhands", streaming=True)
    with open(PATH, "w", encoding="utf-8") as f:
        for i, row in enumerate(ds):
            if i >= N:
                break
            f.write(json.dumps(row) + "\n")

rows = [json.loads(l) for l in open(PATH, encoding="utf-8")]
print(len(rows), "rows")

never, seen = Counter(), Counter()
for row in rows:
    d, u = declared(row), used(row)
    for name in d:
        seen[name] += 1
        if name not in u:
            never[name] += 1

for name, n in seen.most_common():
    print(f"{name:22} unused in {never[name]:4}/{n:4}")