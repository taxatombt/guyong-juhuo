import sys
sys.path.insert(0, 'E:/juhuo')

# Check lessons.py
with open('E:/juhuo/judgment/lessons.py', encoding='utf-8') as f:
    content = f.read()
print(f"lessons.py: {len(content)} chars, ~{content.count(chr(10))} lines")
# Count seed lessons
import re
seeds = re.findall(r'"(type|domain|lesson|antifragile|warning|pattern|bias|correct_behavior)[:\s"]', content, re.IGNORECASE)
print(f"Sample patterns found: {len(seeds)}")
# Show first few lines
lines = content.split('\n')
for i, line in enumerate(lines[:10]):
    print(f"{i+1}: {line}")

# Check _effective_confidence usage
print("\n=== _effective_confidence usage ===")
for i, line in enumerate(lines):
    if 'effective_confidence' in line or '_DECAY' in line:
        print(f"{i+1}: {line}")
