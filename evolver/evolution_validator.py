#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evolution_validator.py — Self-Evolver 验证闭环

核心改进：验证进化是否真的提升了表现

数据流：
    apply_evolved_weights() 应用新规则
        ↓
    记录 evolution_validation (status='pending')
        ↓
    追踪接下来 N 次判决的准确率
        ↓
    verify_evolution() 验证结果
        ↓
    准确率提升 → status='confirmed'
    准确率下降 → 回滚 + status='reverted'
"""

from __future__ import annotations

import logging

log = logging.getLogger("juhuo.evolution_validator")

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

from judgment.judgment_db import get_conn


# ═══════════════════════════════════════════════════════════════════════════
# 配置（优先从集中配置读取）
# ═══════════════════════════════════════════════════════════════════════════

try:
    from judgment.config import VALIDATION_WINDOW, ACCURACY_IMPROVEMENT_THRESHOLD
    VERIFICATION_WINDOW = VALIDATION_WINDOW
    ACCURACY_IMPROVEMENT_THRESHOLD = ACCURACY_IMPROVEMENT_THRESHOLD
except ImportError:
    VERIFICATION_WINDOW = 10
    ACCURACY_IMPROVEMENT_THRESHOLD = 0.05

SELF_MODEL_BACKUP_DIR = Path(__file__).parent.parent / "data" / "self_model_backups"


# ═══════════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EvolutionValidation:
    """进化验证记录"""
    evolution_id: str
    applied_at: str
    pre_accuracy: float
    post_judgments: int = 0
    post_correct: int = 0
    post_accuracy: float = 0.0
    accuracy_delta: float = 0.0
    status: str = "pending"  # pending / confirmed / reverted
    rollback_reason: str = ""
    validated_at: str = ""


# ═══════════════════════════════════════════════════════════════════════════
# 核心函数
# ═══════════════════════════════════════════════════════════════════════════

def start_evolution_tracking(evolution_id: str, pre_accuracy: float) -> bool:
    """
    开始追踪一次进化
    
    在 apply_evolved_weights() 后调用，开始验证流程。
    
    Args:
        evolution_id: 进化ID
        pre_accuracy: 进化前的准确率
        
    Returns:
        True 表示开始追踪成功
    """
    from judgment.judgment_db import get_conn
    
    now = datetime.now().isoformat()
    
    with get_conn() as c:
        c.execute("""
            INSERT INTO evolution_validation 
            (evolution_id, applied_at, pre_accuracy, post_judgments, post_correct, status)
            VALUES (?, ?, ?, 0, 0, 'pending')
        """, (evolution_id, now, pre_accuracy))
        c.commit()
    
    return True


def record_post_verdict(evolution_id: str, correct: bool) -> None:
    """
    记录进化后的判决结果
    
    每次 verdict 后调用，用于累积验证数据。
    
    Args:
        evolution_id: 进化ID
        correct: 判断是否正确
    """
    from judgment.judgment_db import get_conn
    
    with get_conn() as c:
        # 更新统计
        c.execute("""
            UPDATE evolution_validation 
            SET post_judgments = post_judgments + 1,
                post_correct = post_correct + ?
            WHERE evolution_id = ? AND status = 'pending'
        """, (1 if correct else 0, evolution_id))
        
        # 如果达到验证窗口，自动触发验证
        row = c.execute("""
            SELECT post_judgments FROM evolution_validation 
            WHERE evolution_id = ?
        """, (evolution_id,)).fetchone()
        
        if row and row[0] >= VERIFICATION_WINDOW:
            # 自动触发验证
            verify_evolution(evolution_id)


def verify_evolution(evolution_id: str) -> Tuple[bool, str]:
    """
    验证进化是否真的提升了表现
    
    当 post_judgments >= VERIFICATION_WINDOW 时调用。
    
    验证逻辑：
    1. 计算进化后的准确率
    2. 对比进化前的准确率
    3. 如果准确率提升 > 阈值 → confirmed
    4. 如果准确率下降 → 回滚 self_model
    
    Args:
        evolution_id: 进化ID
        
    Returns:
        (success, message)
    """
    log.info(f"Verifying evolution: {evolution_id}")
    from judgment.judgment_db import get_conn
    from self_model.self_model import SelfModel
    
    with get_conn() as c:
        row = c.execute("""
            SELECT * FROM evolution_validation WHERE evolution_id = ?
        """, (evolution_id,)).fetchone()
        
        if not row:
            log.error(f"Evolution not found: {evolution_id}")
            return False, f"Evolution {evolution_id} not found"
        
        if row["status"] != "pending":
            log.info(f"Evolution already verified: {row['status']}")
            return True, f"Evolution already verified: {row['status']}"
        
        pre_accuracy = row["pre_accuracy"]
        post_judgments = row["post_judgments"]
        post_correct = row["post_correct"]
        
        # 计算进化后准确率
        post_accuracy = post_correct / post_judgments if post_judgments > 0 else 0.0
        accuracy_delta = post_accuracy - pre_accuracy
        
        now = datetime.now().isoformat()
        
        # 判断是否需要回滚
        if accuracy_delta >= ACCURACY_IMPROVEMENT_THRESHOLD:
            # 准确率提升，验证通过
            c.execute("""
                UPDATE evolution_validation
                SET post_accuracy = ?, accuracy_delta = ?, status = 'confirmed', validated_at = ?
                WHERE evolution_id = ?
            """, (post_accuracy, accuracy_delta, now, evolution_id))
            c.commit()
            
            return True, f"Evolution confirmed! Δ={accuracy_delta:.2%}"
        
        elif accuracy_delta < -ACCURACY_IMPROVEMENT_THRESHOLD:
            # 准确率下降，需要回滚
            rollback_reason = f"Accuracy dropped: {pre_accuracy:.2%} → {post_accuracy:.2%} (Δ={accuracy_delta:.2%})"
            
            # 回滚 self_model
            rollback_success = _rollback_self_model(evolution_id)
            
            c.execute("""
                UPDATE evolution_validation
                SET post_accuracy = ?, accuracy_delta = ?, status = 'reverted', 
                    validated_at = ?, rollback_reason = ?
                WHERE evolution_id = ?
            """, (post_accuracy, accuracy_delta, now, rollback_reason, evolution_id))
            c.commit()
            
            return rollback_success, f"Evolution reverted! {rollback_reason}"
        
        else:
            # 准确率变化不显著，继续追踪
            return True, f"Evolution inconclusive, continuing tracking. Δ={accuracy_delta:.2%}"


def _rollback_self_model(evolution_id: str) -> bool:
    """
    回滚 self_model 权重到上一版本

    流程：
    1. 备份当前 self_model.json
    2. 从 evolutions/evolved_weights.json history 恢复到上一组权重
    3. 直接写回 self_model.json（只更新 weights 字段）

    如果没有历史记录则备份当前版本并标记失败。
    """
    from self_model.self_model import load_model, save_model
    import shutil

    SELF_MODEL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_FILE = Path(__file__).parent.parent / "self_model.json"
    EVOLVED_WEIGHTS_FILE = Path(__file__).parent.parent / "data" / "evolutions" / "evolved_weights.json"

    # 1. 备份当前模型
    backup_path = SELF_MODEL_BACKUP_DIR / f"{evolution_id}.json"
    try:
        shutil.copy2(MODEL_FILE, backup_path)
    except Exception:
        backup_path.write_text(MODEL_FILE.read_text(encoding="utf-8"))

    # 2. 尝试从 evolved_weights.json history 恢复
    try:
        if EVOLVED_WEIGHTS_FILE.exists():
            with open(EVOLVED_WEIGHTS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            history = data.get("history", [])
            if len(history) >= 2:
                # history[-2] 是"上一版本"（history[-1] 是刚才刚应用的当前版本）
                previous_weights = history[-2].get("weights", {})
                model = load_model()
                model.weights = previous_weights
                save_model(model)
                log.info(f"[rollback] Restored to previous weights from history: {list(previous_weights.keys())}")
                return True
    except Exception as e:
        log.warning(f"[rollback] Failed to restore from history: {e}")

    # 3. fallback：恢复最近一次备份
    try:
        backups = sorted([b for b in SELF_MODEL_BACKUP_DIR.glob("*.json") if b != backup_path])
        if backups:
            latest_backup = backups[-1]
            shutil.copy2(latest_backup, MODEL_FILE)
            log.info(f"[rollback] Restored from backup: {latest_backup.name}")
            return True
    except Exception as e:
        log.error(f"[rollback] Backup restore failed: {e}")

    log.error(f"[rollback] No recovery method succeeded for {evolution_id}")
    return False


def get_evolution_status(evolution_id: str) -> Optional[Dict]:
    """获取进化状态"""
    from judgment.judgment_db import get_conn
    
    with get_conn() as c:
        row = c.execute("""
            SELECT * FROM evolution_validation WHERE evolution_id = ?
        """, (evolution_id,)).fetchone()
        
        if row:
            return dict(row)
        return None


def get_pending_evolutions() -> list:
    """获取所有待验证的进化"""
    from judgment.judgment_db import get_conn
    
    with get_conn() as c:
        rows = c.execute("""
            SELECT * FROM evolution_validation WHERE status = 'pending'
            ORDER BY created_at ASC
        """).fetchall()
        
        return [dict(r) for r in rows]


def force_verify_all() -> Dict[str, Tuple[bool, str]]:
    """
    强制验证所有待验证的进化
    
    Returns:
        {evolution_id: (success, message)}
    """
    results = {}
    for evo in get_pending_evolutions():
        evolution_id = evo["evolution_id"]
        
        # 如果达到验证窗口
        if evo["post_judgments"] >= VERIFICATION_WINDOW:
            success, msg = verify_evolution(evolution_id)
            results[evolution_id] = (success, msg)
    
    return results


# ═══════════════════════════════════════════════════════════════════════════
# 自动集成
# ═══════════════════════════════════════════════════════════════════════════

def add_verdict_to_evolution_tracking(correct: int) -> None:
    """
    verdict 反馈 → 触发进化验证追踪
    
    每次 verdict 反馈时调用，自动更新所有 pending 进化的追踪数据。
    当某条进化的追踪数据达到 VERIFICATION_WINDOW 时，触发验证。
    
    Args:
        correct: 1=正确, 0=错误
    """
    try:
        from judgment.judgment_db import get_conn
        with get_conn() as c:
            # 更新所有 pending 进化
            c.execute("""
                UPDATE evolution_validation
                SET post_judgments = post_judgments + 1,
                    post_correct = post_correct + ?
                WHERE status = 'pending'
            """, (correct,))
            c.commit()
            
            # 检查是否有达到窗口的进化
            rows = c.execute("""
                SELECT evolution_id, post_judgments
                FROM evolution_validation
                WHERE status = 'pending' AND post_judgments >= ?
            """, (VERIFICATION_WINDOW,)).fetchall()
            
            for row in rows:
                verify_evolution(row["evolution_id"])
                
        log.debug(f"[tracker] verdict={correct}, updated {len(rows)} evolutions pending verify")
    except Exception as e:
        log.debug(f"[tracker] skip: {e}")


def on_verdict_recorded(chain_id: str, correct: bool, evolution_ids: list) -> None:
    """
    verdict 记录后的钩子
    
    自动检查是否需要验证进化。
    
    Args:
        chain_id: 判断ID
        correct: 是否正确
        evolution_ids: 相关的进化ID列表
    """
    if not evolution_ids:
        return
    for evo_id in evolution_ids:
        status = get_evolution_status(evo_id)
        if status and status["post_judgments"] >= VERIFICATION_WINDOW:
            verify_evolution(evo_id)
