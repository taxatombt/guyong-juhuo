import sys
sys.path.insert(0, 'E:/juhuo')

# Check verdict_collector.py
from judgment.verdict_collector import mark_verdict_correct, mark_verdict_wrong, receive_actual_choice
import inspect

print("=== mark_verdict_correct source ===")
print(inspect.getsource(mark_verdict_correct))
print()
print("=== mark_verdict_wrong source ===")
print(inspect.getsource(mark_verdict_wrong))
print()
print("=== receive_actual_choice source (first 80 lines) ===")
src = inspect.getsource(receive_actual_choice)
lines = src.split('\n')
print('\n'.join(lines[:80]))
