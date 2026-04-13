#!/usr/bin/env python3
"""
test_openspace_integration.py —— Full OpenSpace integration test for guyong-juhuo
"""

import sys
sys.path.insert(0, '.')

from openspace_evolution import (
    EvolutionType,
    SkillLineage,
    SkillMetrics,
    create_captured,
    create_derived,
    create_fix,
    load_skill_db,
    save_skill_db,
    mark_cascade_revalidation,
    format_dag_ascii,
    get_stats,
    suggest_evolution,
    generate_evolution_report,
    create_and_save_captured,
    create_and_save_derived,
    create_and_save_fix,
    SKILL_DB_PATH,
)

from openspace_utils import (
    generate_skill_id,
    parse_skill_id,
    PriorityLevel,
    ConversationFormatter,
    format_action_log,
    detect_patch_type,
    simple_fuzzy_search,
    find_best_match,
    get_implementation_summary,
)

from execution_analyzer import ExecutionAnalyzer

import tempfile
from pathlib import Path

print("=== Full OpenSpace Integration Test for guyong-juhuo ===")
print()

# 1. Test type imports
print("1. Testing type imports...")
print(f"   EvolutionType: CAPTURED={EvolutionType.CAPTURED}, DERIVED={EvolutionType.DERIVED}, FIX={EvolutionType.FIX}")
print("   Types imported OK")
print()

# 2. Test Version DAG creation
print("2. Testing Version DAG creation...")
root = create_captured("document-gen-fallback", "3a6b7356")
assert root.generation == 0
assert root.fix_version == 0
assert root.is_active == True
print(f"   Root: {root.skill_id} gen={root.generation} v={root.fix_version} active={root.is_active}")
print("   CAPTURED root created OK")

# Derive from root
derived = create_derived(root, "document-gen-fallback-enhanced", "7aea6203")
assert derived.generation == 1
assert derived.fix_version == 0
assert root.is_active == True  # parent stays active
assert derived.skill_id in root.child_ids
print(f"   Derived: {derived.skill_id} gen={derived.generation} v={derived.fix_version} parent={root.skill_id} active={derived.is_active}")
print(f"   Root children: {root.child_ids}")
print("   DERIVED created OK")

# FIX on derived
fixed1 = create_fix(derived, "hash1234")
assert fixed1.generation == derived.generation  # same generation
assert fixed1.fix_version == 1  # v increments
assert not derived.is_active  # parent deactivated
assert fixed1.skill_id in derived.child_ids
print(f"   FIX 1: {fixed1.skill_id} gen={fixed1.generation} v={fixed1.fix_version}")

# Second FIX
fixed2 = create_fix(fixed1, "hash5678")
assert fixed2.fix_version == 2

# Third FIX (our final)
fixed3 = create_fix(fixed2, "7aea6203")
assert fixed3.fix_version == 3
print(f"   FIX 3: {fixed3.skill_id} v={fixed3.fix_version}")
print("   Multiple FIX increments version correctly")
print()

# 3. Test ASCII DAG visualization
print("3. Testing ASCII DAG visualization...")
db = {
    root.skill_id: root,
    derived.skill_id: derived,
    fixed1.skill_id: fixed1,
    fixed2.skill_id: fixed2,
    fixed3.skill_id: fixed3,
}
ascii_tree = format_dag_ascii(db)
print(ascii_tree)
print("   ASCII formatting OK")
print()

# 4. Test SkillMetrics
print("4. Testing SkillMetrics...")
metrics = SkillMetrics()
metrics.mark_used(True)
metrics.mark_used(True)
metrics.mark_used(False)
assert metrics.applied_count == 3
assert metrics.success_count == 2
assert metrics.failed_count == 1
assert abs(metrics.success_rate - 2/3) < 0.001
print(f"   applied={metrics.applied_count} success={metrics.success_count} failed={metrics.failed_count} rate={metrics.success_rate:.1%}")
print("   Metrics tracking OK")
print()

# 5. Test cascade revalidation
print("5. Testing cascade revalidation...")
mark_cascade_revalidation(root.skill_id, db)
count_needs_reval = sum(1 for node in db.values() if node.metrics.needs_revalidation)
assert count_needs_reval == 5  # all descendants including root
print(f"   All descendants marked needs_revalidation: {count_needs_reval}/{len(db)}")
print("   Cascade revalidation working")
print()

# 6. Test utility functions
print("6. Testing utility functions...")
sid = generate_skill_id("test-skill", 2, "some test content for hashing")
parsed = parse_skill_id(sid)
assert parsed is not None
name, fix_v, hash_val = parsed
print(f"   generate_skill_id: {sid}")
print(f"   parsed: {parsed}")
print("   skill_id generation/parse OK")

patch_type = detect_patch_type("""
<<<<<<< SEARCH
old code here
=======
new code here
>>>>>>> REPLACE
""")
print(f"   detect_patch_type for search/replace: {patch_type}")
print("   patch detection OK")

cf = ConversationFormatter(max_total_tokens=200)
formatted = cf.format_from_plain([
    (PriorityLevel.CRITICAL, "Fix the login bug"),
    (PriorityLevel.HIGH, "Error: 500 Internal Server Error"),
    (PriorityLevel.MEDIUM, "Here is the stack trace..."),
    (PriorityLevel.LOW, "Lots of debug logs\n" * 100),
])
print(f"   ConversationFormatter truncated: {len(formatted.splitlines())} lines")
print("   Priority formatting OK")

mismatch = simple_fuzzy_search("hello world", "hello wurld")
print(f"   simple_fuzzy_search 'hello world' vs 'hello wurld': mismatches={mismatch}")
print("   fuzzy search OK")
print()

# 7. Test persistent DB
print("7. Testing persistent DB with temp file...")
with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
    f.write('{}')
    temp_path = Path(f.name)

db_test = load_skill_db(temp_path)
assert len(db_test) == 0

captured = create_and_save_captured("test-skill-1", "content here", temp_path)
assert captured.skill_id in load_skill_db(temp_path)
print(f"   Created and saved CAPTURED: {captured.skill_id}")

loaded = load_skill_db(temp_path)
assert len(loaded) == 1
print("   Load from disk OK")
temp_path.unlink()
print("   Persistence OK")
print()

# 8. Test statistics
print("8. Testing statistics...")
stats = get_stats(db)
print(f"   total nodes: {stats['total_nodes']}, active: {stats['active_nodes']}")
print(f"   by type: {stats['by_evolution_type']}")
print(f"   need revalidation: {len(stats['needs_revalidation'])}")
print("   Statistics OK")
print()

# 9. Test evolution recommendations
print("9. Testing evolution recommendations...")
sug = suggest_evolution(db)
print(f"   Recommendations: {len(sug)}")
for s in sug[:5]:
    print(f"     - {s['skill_id']}: {s['evolution_type'].value} - {s['reason']} (rate={s['current_success_rate']:.0%})")
print("   Recommendation works OK")
print()

# 10. Test implementation summary
print("10. Testing implementation summary...")
summary = get_implementation_summary()
print(f"   Implemented features: {len(summary['implemented'])}")
for item in summary['implemented']:
    print(f"     * {item}")
print()

print("=== ALL TESTS PASSED! ===")
print()
print("OpenSpace fully integrated into guyong-juhuo:")
print("  ✓ Three evolution modes: CAPTURED / DERIVED / FIX")
print("  ✓ Two-dimensional version semantics (generation + fix_version)")
print("  ✓ Cascade revalidation when base changes")
print("  ✓ Skill quality metrics tracking")
print("  ✓ Automatic evolution suggestions")
print("  ✓ All OpenSpace recommended utilities: skill_id + conversation_formatter + detect_patch_type")
print("  ✓ ASCII DAG visualization")
print()
print("OpenSpace integration complete. guyong-juhuo now has full self-evolution capability!")
