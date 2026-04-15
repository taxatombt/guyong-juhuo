#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
security_rule_engine.py - Hookify style rule engine
Source: Claude Code hookify + weekly report 2026-04-14
"""
import re, os, yaml, logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
from functools import lru_cache
from dataclasses import dataclass, field

log = logging.getLogger("security_rule_engine")

@dataclass
class Condition:
    type: Literal["regex_match","contains","equals","not_contains","starts_with","ends_with"]
    field: str = "command"; pattern: str = ""; case_sensitive: bool = False
    def match(self, ctx: Dict[str,Any]) -> bool:
        v = str(ctx.get(self.field) or "")
        if not self.case_sensitive: v = v.lower(); pat = self.pattern.lower()
        else: pat = self.pattern
        t = self.type
        if t == "regex_match":
            try: return bool(re.search(pat, v))
            except re.error: return False
        elif t == "contains": return pat in v
        elif t == "equals": return v == pat
        elif t == "not_contains": return pat not in v
        elif t == "starts_with": return v.startswith(pat)
        elif t == "ends_with": return v.endswith(pat)
        return False

@dataclass
class Rule:
    id: str; description: str; tool: str = "*"
    conditions: List[Condition] = field(default_factory=list)
    action: Literal["block","warn"] = "warn"; message: str = ""
    enabled: bool = True; match_mode: Literal["all","any"] = "all"
    def match(self, ctx: Dict[str,Any]) -> bool:
        if not self.enabled: return False
        if self.tool != "*" and self.tool != ctx.get("tool_name","*"): return False
        if not self.conditions: return False
        fn = all if self.match_mode == "all" else any
        return fn(c.match(ctx) for c in self.conditions)

@dataclass
class EvalResult:
    decision: Literal["allow","block","warn"]; rule_id: Optional[str] = None
    system_message: str = ""; matched_rules: List[str] = field(default_factory=list)
    def to_dict(self) -> Dict:
        return {"decision":self.decision,"rule_id":self.rule_id,
                "systemMessage":self.system_message,"matched_rules":self.matched_rules}

_RULES: Dict[str,Rule] = {}; _LOADED = False

_BUILTIN = [
    {"id":"dangerous_rm","description":"Blocks recursive rm","tool":"Bash",
     "conditions":[{"type":"regex_match","field":"command","pattern":r"rm\s+(-[rf]+\s+)?/"}],
     "action":"block","message":"Recursive rm blocked."},
    {"id":"curl_pipe_sh","description":"Blocks curl|bash","tool":"Bash",
     "conditions":[{"type":"regex_match","field":"command","pattern":r"curl\s+.*\|\s*(bash|sh|zsh)"}],
     "action":"block","message":"curl|bash pipe blocked."},
    {"id":"wget_pipe_sh","description":"Blocks wget|bash","tool":"Bash",
     "conditions":[{"type":"regex_match","field":"command","pattern":r"wget\s+.*\|\s*(bash|sh|zsh)"}],
     "action":"block","message":"wget|bash pipe blocked."},
    {"id":"fork_bomb","description":"Blocks fork bomb","tool":"Bash",
     "conditions":[{"type":"regex_match","field":"command","pattern":r":\(\)\{\s*:\|:&\s*\};"}],
     "action":"block","message":"Fork bomb blocked."},
    {"id":"eval_user_input","description":"Warns on eval user input","tool":"Bash",
     "conditions":[{"type":"regex_match","field":"command","pattern":r"\beval\s+\$\{"}],
     "action":"warn","message":"eval on user input is risky."},
    {"id":"innerHTML","description":"Warns on innerHTML XSS","tool":"*",
     "conditions":[{"type":"contains","field":"content","pattern":"innerHTML"}],
     "action":"warn","message":"innerHTML detected."},
]

def _make(d: Dict) -> Rule:
    cs = [Condition(type=c["type"],field=c.get("field","command"),
                    pattern=c["pattern"],case_sensitive=c.get("case_sensitive",False))
          for c in d.get("conditions",[])]
    return Rule(id=d["id"],description=d.get("description",""),tool=d.get("tool","*"),
                conditions=cs,action=d.get("action","warn"),message=d.get("message",""),
                enabled=d.get("enabled",True),match_mode=d.get("match_mode","all"))

def _load_file(path: str) -> int:
    cnt = 0
    try:
        with open(path, encoding="utf-8") as f: c = f.read()
        if c.strip().startswith("---"):
            parts = c.split("---",2); c = parts[1].strip() if len(parts)>=3 else c.strip()
        data = yaml.safe_load(c)
        if not data: return 0
        for rd in (data if isinstance(data,list) else data.get("rules",[])):
            if not rd.get("enabled",True): continue
            r = _make(rd); _RULES[r.id] = r; cnt += 1
    except Exception as e:
        log.warning(f"Rule load error {path}: {e}")
    return cnt

def init():
    global _LOADED
    if _LOADED: return
    _RULES.clear()
    for d in _BUILTIN:
        r = _make(d); _RULES[r.id] = r
    user = Path.home()/".juhuo"/"security_rules"
    if user.exists():
        for fp in user.glob("**/*"):
            if fp.suffix in (".yaml",".yml",".md"): _load_file(str(fp))
    _LOADED = True
    log.info(f"[security_rule_engine] {len(_RULES)} rules loaded")

def evaluate(ctx: Dict[str,Any]) -> EvalResult:
    if not _LOADED: init()
    blocks, warns = [], []
    for rule in _RULES.values():
        try:
            if rule.match(ctx):
                (blocks if rule.action=="block" else warns).append(rule)
        except: pass
    if blocks:
        r = blocks[0]
        return EvalResult("block",r.id,r.message or f"Blocked: {r.id}",[r.id])
    if warns:
        r = warns[0]
        return EvalResult("warn",r.id,r.message or f"Warning: {r.id}",[x.id for x in warns])
    return EvalResult("allow")

def is_allowed(cmd: str, tool: str="Bash") -> bool:
    return evaluate({"tool_name":tool,"command":cmd}).decision in ("allow","warn")
def is_blocked(cmd: str, tool: str="Bash") -> bool:
    return evaluate({"tool_name":tool,"command":cmd}).decision == "block"
def add_rule(rule: Rule) -> None: _RULES[rule.id] = rule
def remove_rule(rid: str) -> bool:
    if rid in _RULES: del _RULES[rid]; return True
    return False
def get_rules() -> List[Rule]: return list(_RULES.values())
def get_rule(rid: str) -> Optional[Rule]: return _RULES.get(rid)

if __name__ == "__main__":
    import json, sys
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        cmd = sys.argv[2] if len(sys.argv) > 2 else ""
        result = evaluate({"tool_name":"Bash","command":cmd})
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        init()
        print(f"Loaded: {len(_RULES)} rules")
        for r in _RULES.values():
            print(f"  [{r.action.upper():5}] {r.id}")
