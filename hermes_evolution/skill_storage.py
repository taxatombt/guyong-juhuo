"""
Skill Storage for Hermes-style self-evolution

存储、索引、搜索已创建的技能，支持全文搜索和增量更新。
基于 Hermes-Agent 设计：SQLite with FTS5 全文搜索。
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class SkillStorage:
    """SQLite-based skill storage with full-text search."""
    
    def __init__(self, db_path: str = "E:\\juhuo\\hermes_evolution\\skills.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create skills table
            # Create skills table: tags = comma-separated, related_skills = comma-separated
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    version TEXT NOT NULL,
                    author TEXT,
                    category TEXT NOT NULL,
                    tags TEXT,
                    related_skills TEXT,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    usage_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0
                )
            """)
            
            # Create FTS5 virtual table for full-text search
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts 
                USING FTS5(name, description, content, tags, category)
            """)
            
            # Create triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS skills_ai AFTER INSERT ON skills BEGIN
                    INSERT INTO skills_fts(rowid, name, description, content, tags, category)
                    VALUES (new.id, new.name, new.description, new.content, new.tags, new.category);
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS skills_ad AFTER UPDATE ON skills BEGIN
                    UPDATE skills_fts SET
                        name = new.name,
                        description = new.description,
                        content = new.content,
                        tags = new.tags,
                        category = new.category
                    WHERE rowid = old.id;
                END
            """)
            
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS skills_bd AFTER DELETE ON skills BEGIN
                    DELETE FROM skills_fts WHERE rowid = old.id;
                END
            """)
            
            conn.commit()
    
    def add_skill(
        self,
        name: str,
        description: str,
        content: str,
        category: str,
        version: str = "1.0.0",
        author: Optional[str] = None,
        tags: Optional[List[str]] = None,
        related_skills: Optional[List[str]] = None,
    ) -> int:
        """Add a new skill to storage."""
        tags_str = ",".join(tags) if tags else ""
        related_str = ",".join(related_skills) if related_skills else ""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO skills 
                    (name, description, version, author, category, tags, related_skills, content)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, description, version, author, category, tags_str, related_str, content))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Skill already exists, update instead
                cursor.execute("""
                    UPDATE skills SET
                        description = ?,
                        content = ?,
                        category = ?,
                        version = ?,
                        author = ?,
                        tags = ?,
                        related_skills = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                """, (description, content, category, version, author, tags_str, related_str, name))
                conn.commit()
                cursor.execute("SELECT id FROM skills WHERE name = ?", (name,))
                row = cursor.fetchone()
                return row[0] if row else -1
    
    def get_skill(self, name: str) -> Optional[Dict]:
        """Get a skill by name."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM skills WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                skill = dict(row)
                skill["tags"] = skill["tags"].split(",") if skill["tags"] else []
                skill["related_skills"] = skill["related_skills"].split(",") if skill["related_skills"] else []
                # Increment usage count
                cursor.execute("UPDATE skills SET usage_count = usage_count + 1 WHERE id = ?", (skill["id"],))
                conn.commit()
                return skill
            return None
    
    def search_skills(self, query: str, limit: int = 10) -> List[Dict]:
        """Full-text search for skills."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Using FTS5 MATCH query
            cursor.execute("""
                SELECT s.*, rank
                FROM skills s
                JOIN skills_fts f ON s.id = f.rowid
                WHERE f.content MATCH ? OR f.name MATCH ? OR f.description MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, query, query, limit))
            results = []
            for row in cursor:
                skill = dict(row)
                skill["tags"] = skill["tags"].split(",") if skill["tags"] else []
                skill["related_skills"] = skill["related_skills"].split(",") if skill["related_skills"] else []
                results.append(skill)
            return results
    
    def list_skills(self, category: Optional[str] = None) -> List[Dict]:
        """List all skills, optionally filtered by category."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if category:
                cursor.execute("SELECT * FROM skills WHERE category = ? ORDER BY created_at DESC", (category,))
            else:
                cursor.execute("SELECT * FROM skills ORDER BY created_at DESC")
            results = []
            for row in cursor:
                skill = dict(row)
                skill["tags"] = skill["tags"].split(",") if skill["tags"] else []
                skill["related_skills"] = skill["related_skills"].split(",") if skill["related_skills"] else []
                results.append(skill)
            return results
    
    def record_result(self, name: str, success: bool) -> None:
        """Record usage result (success/failure) for learning."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if success:
                cursor.execute("UPDATE skills SET success_count = success_count + 1 WHERE name = ?", (name,))
            else:
                cursor.execute("UPDATE skills SET failure_count = failure_count + 1 WHERE name = ?", (name,))
            conn.commit()
    
    def delete_skill(self, name: str) -> bool:
        """Delete a skill from storage."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM skills WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_stats(self) -> Dict:
        """Get storage statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM skills")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(usage_count) FROM skills")
            total_usage = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(success_count) FROM skills")
            total_success = cursor.fetchone()[0] or 0
            cursor.execute("SELECT SUM(failure_count) FROM skills")
            total_failure = cursor.fetchone()[0] or 0
            cursor.execute("SELECT DISTINCT category FROM skills")
            categories = [row[0] for row in cursor.fetchall()]
            
            return {
                "total_skills": total,
                "total_usage": total_usage,
                "total_success": total_success,
                "total_failure": total_failure,
                "success_rate": (total_success / (total_success + total_failure)) if (total_success + total_failure) > 0 else 0,
                "categories": categories,
            }
