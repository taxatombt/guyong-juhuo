import os, re

path = "E:\\juhuo\\causal_memory\\causal_memory.py"
content = open(path, encoding="utf-8", errors="ignore").read()

# Find all usages of CAUSAL_EVENTS_FILE / CAUSAL_LINKS_FILE / jsonl
lines = content.split("\n")
for i, line in enumerate(lines, 1):
    if any(x in line for x in ["CAUSAL_EVENTS_FILE", "CAUSAL_LINKS_FILE", "jsonl", "JSONL"]):
        print(f"{i}: {line.rstrip()}")

# Check if _schema_tables.py defines causal_events/causal_chains tables
schema_path = "E:\\juhuo\\judgment\\_schema_tables.py"
schema = open(schema_path, encoding="utf-8", errors="ignore").read()
for i, line in enumerate(schema.split("\n"), 1):
    if any(x in line.lower() for x in ["causal_event", "causal_chain", "causal_link"]):
        print(f"_schema_tables.py:{i}: {line.rstrip()}")
