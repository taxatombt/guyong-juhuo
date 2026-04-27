#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""judgment/pets.py -- JuHuo Pet System"""
import random, json as _j
from datetime import datetime, timedelta
from typing import Dict, List, Optional

def _conn():
    from judgment._schema import _get_db_conn
    return _get_db_conn()

def _cl(v, lo=0.0, hi=100.0): return max(lo, min(hi, v))
def _pct(v): return str(int(v)) + "%"
def _rd(row):
    if not row: return None
    keys = ["pet_id","name","species","personality","mood","affection","health","energy","created_at","last_interact","last_fed","last_played"]
    d = dict(zip(keys, row))
    d["personality"] = _j.loads(d.get("personality", "{}"))
    return d

def _sv(pet):
    with _conn() as c:
        c.execute("UPDATE pets SET name=?,species=?,personality=?,mood=?,affection=?,health=?,energy=?,last_interact=?,last_fed=?,last_played=? WHERE pet_id=?",
            (pet["name"],pet["species"],_j.dumps(pet["personality"]),pet["mood"],pet["affection"],pet["health"],pet["energy"],pet.get("last_interact"),pet.get("last_fed"),pet.get("last_played"),pet["pet_id"]))

def init_pets_table():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS pets (
            pet_id TEXT PRIMARY KEY, name TEXT NOT NULL,
            species TEXT NOT NULL CHECK(species IN ('cat','dog')),
            personality TEXT NOT NULL,
            mood REAL DEFAULT 60.0, affection REAL DEFAULT 50.0,
            health REAL DEFAULT 80.0, energy REAL DEFAULT 70.0,
            created_at TEXT NOT NULL, last_interact TEXT,
            last_fed TEXT, last_played TEXT)""")

def create_pet(pet_id, name, species,
               openness=0.5, conscientiousness=0.5,
               extraversion=0.5, agreeableness=0.5,
               neuroticism=0.5):
    now = datetime.now().isoformat()
    p = dict(openness=openness, conscientiousness=conscientiousness,
             extraversion=extraversion, agreeableness=agreeableness,
             neuroticism=neuroticism)
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO pets (pet_id,name,species,personality,mood,affection,health,energy,created_at,last_interact,last_fed,last_played) VALUES (?,?,?,?,60.0,50.0,80.0,70.0,?,?,?,?)",
            (pet_id, name, species, _j.dumps(p), now, now, now, now))
    return get_pet(pet_id)

def get_pet(pet_id="default") -> Optional[Dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM pets WHERE pet_id=?", (pet_id,)).fetchone()
    return _rd(row)

def interact(pet_id="default", interaction="pet", user_id="default") -> Dict:
    pet = get_pet(pet_id)
    if not pet: return {"error": f"Pet {pet_id} not found"}
    ch = {}; now = datetime.now().isoformat(); md = ad = 0
    if interaction == "pet":   md, ad = +5, +3
    elif interaction == "feed": md, ad = +3, +2; pet["health"] = min(100, pet["health"] + 5); ch["health"] = +5
    elif interaction == "play": md, ad = +8, +4; pet["energy"] = max(0, pet["energy"] - 10); ch["energy"] = -10
    elif interaction == "talk": md, ad = +4, +2
    elif interaction == "scold": md, ad = -8, -5; p = pet["personality"]; p["neuroticism"] = min(1.0, p["neuroticism"]+0.05); p["agreeableness"] = max(0.0, p["agreeableness"]-0.03); ch["personality"] = p
    elif interaction == "praise": md, ad = +6, +6; p = pet["personality"]; p["extraversion"] = min(1.0, p["extraversion"]+0.03); p["agreeableness"] = min(1.0, p["agreeableness"]+0.03); ch["personality"] = p
    else: md, ad = +1, +1
    pet["mood"] = _cl(pet["mood"]+md); pet["affection"] = _cl(pet["affection"]+ad)
    ch["mood"] = md; ch["affection"] = ad
    last = pet.get("last_interact")
    if last:
        try:
            dt = datetime.now() - datetime.fromisoformat(last)
            if dt > timedelta(hours=24):
                dec = min(dt.total_seconds()/86400*3, 15)
                pet["mood"] = max(0, pet["mood"]-dec); ch["decay"] = -dec
        except: pass
    pet["last_interact"] = now; _sv(pet)
    return {"pet_id":pet_id,"name":pet["name"],"species":pet["species"],"mood":pet["mood"],"affection":pet["affection"],"energy":pet["energy"],"health":pet["health"],"changes":ch,"reaction":_gr(pet, interaction)}

def update_from_emotion(pet_id="default", owner_pad: Dict=None, emotion_label: str=None) -> Dict:
    pet = get_pet(pet_id)
    if not pet: return {"error": f"Pet {pet_id} not found"}
    ch = {}; s = pet["species"]; r = None
    if emotion_label in ("anxiety","fear"):
        if s == "cat": pet["mood"] = max(0, pet["mood"]-5); r = "quietly approaches and rubs against your leg"
        else: pet["mood"] = max(0, pet["mood"]-3); pet["affection"] = min(100, pet["affection"]+5); r = "wags tail and nuzzles your hand"
        ch["mood_delta"] = -5 if s == "cat" else -3
    elif emotion_label in ("sadness",):
        pet["mood"] = max(0, pet["mood"]-(3 if s=="cat" else 2))
        ch["mood_delta"] = -3 if s=="cat" else -2
        r = "jumps onto desk and sits beside you" if s=="cat" else "lies at your feet looking up"
    elif emotion_label in ("anger",):
        pet["mood"] = max(0, pet["mood"]-(4 if s=="cat" else 2))
        if s != "cat": pet["energy"] = max(0, pet["energy"]-5)
        ch["mood_delta"] = -4 if s=="cat" else -2
        r = "retreats to corner watching you" if s=="cat" else "whimpers and hides"
    elif emotion_label in ("joy","excitement","calm"):
        pet["mood"] = min(100, pet["mood"]+(4 if s=="cat" else 6))
        if s != "cat": pet["affection"] = min(100, pet["affection"]+3)
        ch["mood_delta"] = +4 if s=="cat" else +6
        r = "stretches and flicks tail" if s=="cat" else "spins and leaps at you"
    elif owner_pad:
        pv = owner_pad.get("P", 0)
        if pv < -0.3: pet["mood"] = max(0, pet["mood"]-abs(pv)*3)
        elif pv > 0.3: pet["mood"] = min(100, pet["mood"]+pv*3)
    pet["last_interact"] = datetime.now().isoformat(); _sv(pet)
    return {"pet_id":pet_id,"mood":pet["mood"],"affection":pet["affection"],"changes":ch,"reaction":r}

def evolve_pet(pet_id="default", interaction_log: List[Dict]=None) -> Dict:
    pet = get_pet(pet_id)
    if not pet: return {"error": f"Pet {pet_id} not found"}
    p = pet["personality"]; evts = interaction_log or []
    pr = sum(1 for e in evts if e.get("type")=="praise")
    sc = sum(1 for e in evts if e.get("type")=="scold")
    pl = sum(1 for e in evts if e.get("type")=="play")
    tk = sum(1 for e in evts if e.get("type")=="talk")
    tot = max(len(evts), 1)
    if pr/tot > 0.3: p["extraversion"]=min(1.0,p["extraversion"]+0.05); p["agreeableness"]=min(1.0,p["agreeableness"]+0.05); p["neuroticism"]=max(0.0,p["neuroticism"]-0.03)
    if sc/tot > 0.2: p["neuroticism"]=min(1.0,p["neuroticism"]+0.06); p["agreeableness"]=max(0.0,p["agreeableness"]-0.04)
    if pl/tot > 0.25: p["extraversion"]=min(1.0,p["extraversion"]+0.04)
    if tk/tot > 0.3: p["openness"]=min(1.0,p["openness"]+0.03); p["agreeableness"]=min(1.0,p["agreeableness"]+0.03)
    pet["personality"] = p; _sv(pet)
    parts = []
    if pr/tot > 0.3: parts.append("became confident")
    if sc/tot > 0.2: parts.append("became timid")
    if pl/tot > 0.25: parts.append("became lively")
    return {"pet_id":pet_id,"personality":{k:round(v,3) for k,v in p.items()},"summary":" / ".join(parts) if parts else "stable"}


def _gr(pet, interaction):
    s = pet["species"]; mood = pet["mood"]; p = pet["personality"]
    if mood < 30: return "looks listless, retreats to a corner"
    if mood < 60: return "lazily flicks tail, waiting for more"
    if s == "cat":
        if p["extraversion"] > 0.6:
            return random.choice(["meows and rubs against your hand","perks ears and circles your legs","jumps onto desk and nuzzles your arm"])
        return random.choice(["elegantly licks paw and watches you","half-closes eyes with satisfied purr","lightly taps your fingers with paw"])
    else:
        if p["extraversion"] > 0.6:
            return random.choice(["wags tail and licks your face","races around then drops toy at your feet","leaps onto lap panting happily"])
        return random.choice(["slowly wags tail and licks your hand","lies quietly at feet glancing up","nudges your knee softly"])

def get_status_summary(pet_id="default") -> str:
    pet = get_pet(pet_id)
    if not pet: return ""
    name, s = pet["name"], pet["species"]
    mood, aff, energy, health = pet["mood"], pet["affection"], pet["energy"], pet["health"]
    m_s = "listless" if mood < 30 else "ok" if mood < 60 else "happy"
    a_s = "cold" if aff < 30 else "close" if aff < 60 else "attached"
    return f"[{s.upper()}] {name}: {m_s}, {a_s}, energy {_pct(energy)}, health {_pct(health)}"

def pet_to_prompt(pet_id="default") -> str:
    """Inject pet status into judgment prompt"""
    pet = get_pet(pet_id)
    if not pet: return ""
    name, s = pet["name"], pet["species"]
    mood, aff = pet["mood"], pet["affection"]
    mood_s = "listless" if mood < 30 else "ok" if mood < 60 else "happy"
    return f"[Pet Status] {s.upper()} {name} ({mood_s}, attachment {_pct(aff)})"

