# guyong-juhuo · Judgement System

**An evolving personal AI agent that mimics a specific individual, then surpasses human-level judgment.**

> Not a tool. A digital alter-ego that grows over time.

---

## What It Is

guyong-juhuo is a **12-subsystem AI agent framework** built on top of LLM backends (MiniMax / OpenAI / Ollama). It simulates the judgment patterns of a specific individual across 10 cognitive dimensions, then improves itself through a closed feedback loop until its judgment exceeds human-level overall.

The core distinction: most AI agents optimize for "what is correct." guyong-juhuo optimizes for **"what would this specific person decide, and why"** — then closes the loop so the system gets better over time.

---

## The 12 Subsystems

| # | Subsystem | What It Does |
|---|-----------|--------------|
| 1 | **Judgment** | 10-dimension parallel evaluation (cognitive · game-theory · economic · dialectical · emotional · intuitive · moral · social · temporal · metacognitive) |
| 2 | **Causal Memory** | Fast/slow dual-stream: instant logging + batch causal inference across events |
| 3 | **Curiosity Engine** | Dual random walk (80% goal-driven / 20% free exploration), Ralph loop termination |
| 4 | **Goal System** | Onion-layered: 5-year → annual → monthly → weekly → today |
| 5 | **Self-Model** | Bayesian blind-spot tracking; accumulates "I tend to err here" patterns |
| 6 | **Emotion System** | PAD 3D model (Pleasure × Arousal × Dominance); emotions as signal, not noise |
| 7 | **Self-Evolution** | Closed-loop: every error → analyzed → rule written → next instance prevented |
| 8 | **Output System** | Decides when to speak and when to stay silent; P0–P4 priority formatter |
| 9 | **Action System** | Four-quadrant urgency × importance sorting + execution signal generation |
| 10 | **Perception Layer** | Attention filter + web adapter + PDF adapter + RSS + email adapters |
| 11 | **Skill Evolution** | Auto-detects skill collision + autonomously improves underperforming skills |
| 12 | **Feedback System** | Dual-loop: judgment layer + evolution layer, 5-layer self-defense hooks |

---

## Two Modes

| Mode | Description |
|------|-------------|
| **Mimic Mode** | Pass in `agent_profile` — the system forces alignment to that individual's judgment style |
| **Transcend Mode** | 10 generic dimensions; no profile — system judges on pure reasoning and closes the loop until it outperforms humans |

**The iron law:** *Mimic a specific individual. Transcend humanity as a whole.*

---

## Quick Start

```bash
git clone https://github.com/taxatombt/guyong-juhuo.git
cd guyong-juhuo
pip install -r requirements.txt

# Judge a dilemma from CLI
python cli.py "Should I take this job offer or keep looking?"

# Run the web console
python hub.py web

# Check dimension belief status
python hub.py verdict --show

# First-time setup wizard
python hub.py config wizard
```

---

## Judgment Output Example

```
=== Judgement: "Should I take this job offer or keep looking?" ===

  cognitive       ████████████████░░  82%  "Need more salary data"
  game_theory     █████████████░░░░░  75%  "Counter-offer risk"
  economic        ████████████████░░  85%  "35% salary gap justifies search"
  dialectical     ███████████████░░░  78%  "Both sides have merit"
  emotional       ████████████░░░░░░  65%  "Anxiety about regret"
  intuitive      ███████████████░░░  80%  "Something better out there"
  moral           ████████████░░░░░░  70%  "Obligation to family"
  social          ██████████░░░░░░░░  60%  "Network opportunity cost"
  temporal        ██████████████░░░  72%  "3-month window optimal"
  metacognitive   ███████████████░░░  79%  "Overconfident in current analysis"

  → RECOMMEND: Keep looking (confidence: HIGH, 81%)
  → chain_id: j_1776149590792
```

---

## Architecture

```
Perception  →  Attention Filter  →  Judgment (10D)
                                           ↓
                                    Causal Memory
                                           ↓
                                     Self-Model
                                           ↓
                                   Closed Feedback Loop
                                    ↕ (verdict signals)
                                   Evolver
                                           ↓
                                   Skill Evolution
```

The closed loop: judgment is made → chain is recorded → user sends post-hoc verdict → beliefs update → next judgment reflects learned adjustment.

---

## Tech Stack

- **Python 3.11+** (core logic)
- **MiniMax / OpenAI / Ollama** (LLM backends)
- **Flask** (web console)
- **SQLite** (judgment chain + belief rolling buffer)
- **PyInstaller** (single-file `.exe` distribution)
- **Inno Setup** (installer)

---

## Installation

### Installer (recommended for Windows)
Download `dist/guyong-juhuo-1.0.0-setup.exe` (~46 MB) → run → next, next, done.

### Portable executable
Download `dist/guyong-juhuo.exe` (~40 MB) → double-click → runs without installation.

### From source
```bash
pip install -r requirements.txt
python hub.py web
# Open http://localhost:18768
```

---

## Configuration

```
~/.juhuo/.env       — API keys (highest priority, never committed to git)
~/.juhuo/config.yaml — user settings
```

Or run the interactive wizard: `python hub.py config wizard`

---

## CLI Reference

```bash
python hub.py                    # Start web console (default, port 18768)
python hub.py web                # Web console (explicit)
python hub.py web --port 8080    # Custom port
python hub.py config show         # Show current config
python hub.py config wizard       # First-time setup wizard
python hub.py config set key val # Set a config value
python hub.py verdict --show      # View dimension belief status
python hub.py verdict -c <id> -w  # Mark a judgment as wrong
python hub.py verdict -c <id> -k  # Mark a judgment as correct
python hub.py upgrade --dry-run   # Check for updates
python hub.py upgrade --force     # Force upgrade to latest
```

---

## Design Principles

- **Iron law protects core identity** — certain traits cannot be evolved away from
- **Fitness = "consistent with who you are"** — not "what general-purpose standards deem correct"
- **Full version snapshots** — any past state of the system is recoverable
- **Judgment chain rolling buffer** — SQLite, 100 entries max, bounded file size
- **Bounded belief updates** — max 10% change per verdict, saturation at 0.05 / 0.95
