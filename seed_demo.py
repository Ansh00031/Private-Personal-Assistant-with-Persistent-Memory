# path: seed_demo.py
"""Seed demo dataset with realistic personal assistant memories and schedules.
Contains sample, fictitious data only (no real personal info).
"""

from memory.db import init_db, get_connection, transaction


def seed_demo_data():
    """Populate sample memories, episodes, notes, and events for demo mode."""
    init_db()

    with transaction() as conn:
        # Check if already seeded
        existing = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
        if existing > 0:
            print("Demo database already has data, skipping seeding.")
            return

        # 1. Sample Memories (User & Assistant interactions)
        sample_memories = [
            ("I prefer waking up at 7:00 AM and having green tea before starting deep work.", "user_said"),
            ("I am leading a team working on an autonomous drone delivery startup.", "user_said"),
            ("My technical stack consists of Python, FastAPI, PyTorch, and NVIDIA Nemotron models.", "user_said"),
            ("Remind me that my mentor meeting happens every Tuesday afternoon at 3 PM.", "user_said"),
            ("I avoid heavy meals during lunch to maintain high focus for afternoon coding.", "user_said"),
        ]

        for content, prov in sample_memories:
            cur = conn.execute("INSERT INTO memories (content, provenance) VALUES (?, ?)", (content, prov))
            mem_id = cur.lastrowid
            # Seed episode fact
            conn.execute(
                "INSERT INTO episodes (fact, memory_id, confidence) VALUES (?, ?, 0.95)",
                (content, mem_id)
            )

        # 2. Sample Notes
        sample_notes = [
            "Project Milestones: 1. Model inference tuning, 2. Memory encryption verification, 3. Video demo recording.",
            "Reading List: 'Attention Is All You Need', 'SQLCipher internals & page architecture', 'Nemotron 3 technical report'.",
        ]
        for note in sample_notes:
            conn.execute("INSERT INTO notes (content) VALUES (?)", (note,))

        # 3. Sample Events
        sample_events = [
            ("Morning Deep Work Session", "2026-10-24 08:30:00", "Focus block: AI Hackathon code completion"),
            ("Team Sync & Demo Review", "2026-10-24 15:00:00", "Review Devpost pitch video and submission deck"),
            ("Submission Deadline Prep", "2026-10-30 09:00:00", "Final submission checklist verification"),
        ]
        for title, start_time, desc in sample_events:
            conn.execute(
                "INSERT INTO events (title, start_time, description) VALUES (?, ?, ?)",
                (title, start_time, desc)
            )

        conn.commit()
        print("Demo database successfully seeded with realistic sample data.")


if __name__ == "__main__":
    seed_demo_data()
