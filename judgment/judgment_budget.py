"""Shim: judgment/judgment_budget.py → subsystems/judgment/judgment_budget"""
import sys
from pathlib import Path
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
from subsystems.judgment.judgment_budget import (
    JudgmentBudget, BudgetExceeded, get_budget,
    budget_protected, check_budget
)
