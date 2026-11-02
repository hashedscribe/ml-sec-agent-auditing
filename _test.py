from datasets import load_dataset
from dotenv import load_dotenv
from load import declared, used

load_dotenv()

NAME = "ArkhAngelLifeJiggy/Open-SWE-Traces"

# v1.2 ['minisweagent']
# v1.1 ['openhands', 'sweagent', 'minisweagent']
# v1.0 ['openhands', 'sweagent']

ds = load_dataset(NAME, "v1.0", split="openhands", streaming=True)

row = next(iter(ds))
for k, v in row.items():
    print(f"{k:20} {type(v).__name__:6} {str(v)[:120]}")

d, u = declared(row), used(row)
print("declared:", sorted(d))
print("used    :", sorted(u))
print("unused  :", sorted(d - u))
print("undeclared:", sorted(u - d))