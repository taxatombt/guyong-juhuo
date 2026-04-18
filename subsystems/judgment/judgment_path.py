#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judgment_path.py — 判断路径定义

一条路径就是一个从关键词到方法的映射：哪些关键词触发调用哪些维度
"""

from dataclasses import dataclass
from typing import List


@dataclass
class JudgmentPath:
    """一条判断路径"""
    id: str
    name: str
    trigger: List[str]
    questions: List[str]
    methods: List[str]
    verify: str
    description: str

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "trigger": self.trigger,
            "questions": self.questions,
            "methods": self.methods,
            "verify": self.verify,
            "description": self.description,
        }
