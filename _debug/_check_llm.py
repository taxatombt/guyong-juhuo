import sys
sys.path.insert(0, 'E:/juhuo')

with open('E:/juhuo/judgment/llm_calls.py', encoding='utf-8') as f:
    content = f.read()
print(f"llm_calls.py: {len(content)} chars, ~{content.count(chr(10))} lines")
print("=== _build_answer_prompt first 150 lines ===")
lines = content.split('\n')
in_func = False
count = 0
for i, line in enumerate(lines):
    if 'def _build_answer_prompt' in line:
        in_func = True
    if in_func:
        print(f"{i+1}: {line}")
        count += 1
        if count > 150:
            print("... [truncated]")
            break
