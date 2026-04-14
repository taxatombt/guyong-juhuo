# 查找 cli.py 中 judgment 输出格式
with open('cli.py', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    if 'check10d' in line or 'format_report' in line:
        print(f"{i}: {line.rstrip()}")
