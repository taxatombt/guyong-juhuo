
import sys
sys.path.insert(0, '.')

print("Testing imports...")
from openspace import record_skill_execution
print("OK: record_skill_execution found")

from openspace import ExecutionAnalyzer
print("OK: ExecutionAnalyzer found")

print("\nAll imports OK!")
