import json, os
from collections import Counter
from dotenv import load_dotenv
from datasets import load_dataset
from load import declared, used

load_dotenv()

NAME = "nvidia/Open-SWE-Traces"
CONFIG = "v2.0"
SPLIT = "claudecode"
N = 1000
PATH = f"samples/sample_{CONFIG}_{SPLIT}.jsonl"

if not os.path.exists(PATH):
    ds = load_dataset(NAME, CONFIG, split=SPLIT, streaming=True)
    with open(PATH, "w", encoding="utf-8") as f:
        for i, row in enumerate(ds):
            if i >= N:
                break
            f.write(json.dumps(row) + "\n")

rows = [json.loads(l) for l in open(PATH, encoding="utf-8")]
print(len(rows), "rows")