"""
Initialize the database and seed static data.

Usage:
    python init_db.py

This script:
  - Creates all tables (if they don't exist yet)
  - Loads questions from locales/questions.json into the questions table

It does NOT create any default project leaders; those are managed
by the admin via the web UI.
"""

import json
import os
import sys

# Ensure the project root is on the path when run directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db
from models.models import Question


def load_questions(questions_path: str) -> None:
    """Read questions.json and upsert rows into the questions table."""
    if not os.path.exists(questions_path):
        print(f"WARNING: {questions_path} not found - no questions loaded.")
        return

    with open(questions_path, encoding="utf-8") as f:
        data = json.load(f)

    # Expected format: list of {"id": "q1", "sort_order": 1, ...}
    # The translations live in the same file but are not stored in the DB.
    questions = data if isinstance(data, list) else data.get("questions", [])

    inserted = 0
    updated = 0
    for entry in questions:
        question_id = entry.get("id")
        sort_order = entry.get("sort_order")

        if not question_id or sort_order is None:
            print(f"  SKIP: invalid entry {entry}")
            continue

        existing = db.session.get(Question, question_id)
        if existing:
            existing.sort_order = sort_order
            updated += 1
        else:
            db.session.add(Question(id=question_id, sort_order=sort_order))
            inserted += 1

    db.session.commit()
    print(f"  Questions: {inserted} inserted, {updated} updated.")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    questions_path = os.path.join(base_dir, "locales", "questions.json")

    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("  Done.")

        print("Loading questions...")
        load_questions(questions_path)

    print("Database initialisation complete.")


if __name__ == "__main__":
    main()
