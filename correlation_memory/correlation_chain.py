# causal_chain.py - #3 causal chain tracing
import json as _j
from pathlib import Path
CACHE_FILE = Path(__file__).parent / "data" / "causal_cache.json"

def _lc():
    if not CACHE_FILE.exists():
        return {}
    with open(CACHE_FILE, encoding="utf-8") as f:
        return _j.load(f)

def _sc(c):
    CACHE_FILE.parent.mkdir(exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        _j.dump(c, f, ensure_ascii=False, indent=2)

def build_causal_chain(result):
    scores = result.get("scores", {})
    weights = result.get("weights", {})
    dimensions = result.get("dimensions", {})
    task = result.get("task", "")

    chain, root_causes, key_levers = [], [], []
    sorted_dims = sorted(scores.items(), key=lambda x: x[1])
    total_impact = sum((1 - s) * weights.get(d, 0.5) for d, s in sorted_dims) or 1.0

    for dim_id, score in sorted_dims:
        dim_info = dimensions.get(dim_id, {}) if isinstance(dimensions, dict) else {}
        weight = weights.get(dim_id, 0.5)
        impact = (1 - score) * weight
        impact_pct = impact / total_impact

        if score < 0.3:
            reason = "Low score + high weight = major barrier"
            root_causes.append(dim_id)
        elif score < 0.5:
            reason = "Below threshold, needs attention"
        else:
            reason = "Above threshold, not a concern"

        dim_name = dim_info.get("name", dim_id) if isinstance(dim_info, dict) else str(dim_info)
        chain.append({
            "dimension": dim_id,
            "dimension_name": dim_name,
            "score": round(score, 3),
            "weight": round(weight, 3),
            "impact": round(impact, 3),
            "impact_pct": round(impact_pct, 3),
            "reason": reason,
            "contributes_to": "final_verdict",
        })

        if impact_pct > 0.2 and score > 0.5:
            key_levers.append(dim_id)

    rc_names = [c["dimension_name"] for c in chain if c["dimension"] in root_causes]
    summary = "Root causes: " + ", ".join(rc_names[:3]) if rc_names else "No major root causes"

    return {
        "task": task,
        "chain": chain,
        "root_causes": root_causes,
        "key_levers": key_levers,
        "summary": summary,
    }

def format_causal_report(chain_result):
    lines = ["=== Correlation Chain Report ===", ""]
    lines.append("Task: " + chain_result.get("task", "")[:60])
    lines.append("Summary: " + chain_result.get("summary", ""))
    lines.append("")
    if chain_result.get("root_causes"):
        lines.append("Root Causes (%d):" % len(chain_result["root_causes"]))
        for c in chain_result["chain"]:
            if c["dimension"] in chain_result["root_causes"]:
                lines.append("  [ROOT] %s: score=%.0f%% impact=%.0f%%" % (
                    c["dimension_name"], c["score"] * 100, c["impact_pct"] * 100))
    if chain_result.get("key_levers"):
        lines.append("")
        lines.append("Key Levers (%d):" % len(chain_result["key_levers"]))
        for c in chain_result["chain"]:
            if c["dimension"] in chain_result["key_levers"]:
                lines.append("  [LEVER] %s: score=%.0f%% impact=%.0f%%" % (
                    c["dimension_name"], c["score"] * 100, c["impact_pct"] * 100))
    lines.append("")
    lines.append("Full Chain:")
    for c in chain_result.get("chain", []):
        bar = "#" * int(c["impact_pct"] * 30)
        lines.append("  %-12s %5.0f%% %-30s %s" % (
            c["dimension_name"][:12], c["score"] * 100, bar, c["reason"][:40]))
    return "\n".join(lines)

# ── CLI re-exports (judgment/closed_loop 中的函数) ──
# Lazy import 避免触发 judgment/llm_adapter 链
def get_recent_chains(limit=10, user_id="default"):
    from subsystems.judgment.closed_loop import get_recent_chains as _f
    return _f(limit=limit, user_id=user_id)

def get_chain_detail(chain_id: str, user_id: str = "default") -> dict:
    from subsystems.judgment.closed_loop import get_recent_chains as _f
    chains = _f(limit=9999, user_id=user_id)
    for c in chains:
        if c.get("chain_id") == chain_id:
            return c
    return {"chain_id": chain_id, "task": "(not found)"}
