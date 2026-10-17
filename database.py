import json
import os
import sqlite3
from datetime import datetime, timezone

import pandas as pd


DB_NAME = os.environ.get("AEROSPEC_DB_PATH", "aerospec_audit.db")


def init_db() -> None:
    """Create the local audit table if it does not already exist."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spec_audits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                title TEXT NOT NULL,
                subsystem TEXT NOT NULL,
                regime TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                ambiguity_score REAL NOT NULL,
                missing_units_count INTEGER NOT NULL,
                vague_words_found TEXT NOT NULL,
                ai_confidence REAL,
                gaps_json TEXT NOT NULL,
                questions_json TEXT NOT NULL
            )
            """
        )


def save_audit(
    title: str,
    subsystem: str,
    regime: str,
    raw_text: str,
    logic_results: dict,
    ai_results: dict | None,
) -> int:
    """Persist one audit and return its new database ID."""
    ai_results = ai_results or {}
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.execute(
            """
            INSERT INTO spec_audits (
                timestamp, title, subsystem, regime, raw_text,
                ambiguity_score, missing_units_count, vague_words_found,
                ai_confidence, gaps_json, questions_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                title,
                subsystem,
                regime,
                raw_text,
                logic_results["ambiguity_score"],
                len(logic_results["missing_unit_numbers"]),
                json.dumps(logic_results["vague_words_found"]),
                ai_results.get("confidence_score"),
                json.dumps(ai_results.get("identified_gaps", [])),
                json.dumps(ai_results.get("clarifying_questions", [])),
            ),
        )
        return int(cursor.lastrowid)


def get_all_audits() -> pd.DataFrame:
    """Return audit records newest first."""
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query(
            "SELECT * FROM spec_audits ORDER BY id DESC",
            conn,
        )
