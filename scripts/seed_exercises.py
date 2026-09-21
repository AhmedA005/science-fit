"""
Seed script: load the curated exercise database into PostgreSQL.

Reads data/exercises.json and inserts:
  - Muscle rows
  - Exercise rows  
  - ExerciseMuscle junction rows (primary/secondary)

Usage:
    python scripts/seed_exercises.py

Safe to re-run -- uses INSERT ... ON CONFLICT DO NOTHING so duplicates are skipped.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path so src imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.progress import track
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Config
from src.database import AsyncSessionLocal
from src.models import Exercise, ExerciseMuscle, Muscle

console = Console()

DATA_FILE = Path(__file__).parent.parent / "data" / "exercises.json"


async def seed_muscles(session: AsyncSession, muscles_data: list[dict]) -> dict[str, int]:
    """Insert muscles, return name -> id mapping."""
    name_to_id: dict[str, int] = {}

    for m in track(muscles_data, description="Seeding muscles..."):
        result = await session.execute(
            text("""
                INSERT INTO muscles (name, muscle_group)
                VALUES (:name, :muscle_group)
                ON CONFLICT (name) DO UPDATE SET muscle_group = EXCLUDED.muscle_group
                RETURNING id
            """),
            {"name": m["name"], "muscle_group": m["muscle_group"]},
        )
        row = result.fetchone()
        name_to_id[m["name"]] = row[0]

    return name_to_id


async def seed_exercises(
    session: AsyncSession,
    exercises_data: list[dict],
    muscle_id_map: dict[str, int],
) -> None:
    """Insert exercises and their muscle junction rows."""

    for ex in track(exercises_data, description="Seeding exercises..."):
        # Upsert the exercise
        result = await session.execute(
            text("""
                INSERT INTO exercises (
                    name, movement_pattern, equipment, exercise_type,
                    difficulty, instructions, bilateral, beginner_friendly
                ) VALUES (
                    :name, :movement_pattern, :equipment, :exercise_type,
                    :difficulty, :instructions, :bilateral, :beginner_friendly
                )
                ON CONFLICT (name) DO UPDATE SET
                    movement_pattern = EXCLUDED.movement_pattern,
                    equipment        = EXCLUDED.equipment,
                    exercise_type    = EXCLUDED.exercise_type,
                    difficulty       = EXCLUDED.difficulty,
                    instructions     = EXCLUDED.instructions,
                    bilateral        = EXCLUDED.bilateral,
                    beginner_friendly = EXCLUDED.beginner_friendly
                RETURNING id
            """),
            {
                "name": ex["name"],
                "movement_pattern": ex["movement_pattern"],
                "equipment": ex["equipment"],
                "exercise_type": ex["exercise_type"],
                "difficulty": ex["difficulty"],
                "instructions": ex.get("instructions"),
                "bilateral": ex["bilateral"],
                "beginner_friendly": ex["beginner_friendly"],
            },
        )
        exercise_id = result.fetchone()[0]

        # Delete existing muscle links (clean re-seed)
        await session.execute(
            text("DELETE FROM exercise_muscles WHERE exercise_id = :eid"),
            {"eid": exercise_id},
        )

        # Insert primary muscles
        for muscle_name in ex.get("primary_muscles", []):
            muscle_id = muscle_id_map.get(muscle_name)
            if muscle_id is None:
                console.print(f"[yellow]Warning: muscle '{muscle_name}' not found for '{ex['name']}'[/yellow]")
                continue
            await session.execute(
                text("""
                    INSERT INTO exercise_muscles (exercise_id, muscle_id, role)
                    VALUES (:eid, :mid, 'primary')
                    ON CONFLICT DO NOTHING
                """),
                {"eid": exercise_id, "mid": muscle_id},
            )

        # Insert secondary muscles
        for muscle_name in ex.get("secondary_muscles", []):
            muscle_id = muscle_id_map.get(muscle_name)
            if muscle_id is None:
                continue
            await session.execute(
                text("""
                    INSERT INTO exercise_muscles (exercise_id, muscle_id, role)
                    VALUES (:eid, :mid, 'secondary')
                    ON CONFLICT DO NOTHING
                """),
                {"eid": exercise_id, "mid": muscle_id},
            )


async def main() -> None:
    console.print("[bold blue]Science-Fit Exercise Seeder[/bold blue]")
    console.print(f"Reading from: {DATA_FILE}")

    if not DATA_FILE.exists():
        console.print(f"[red]Error: {DATA_FILE} not found.[/red]")
        sys.exit(1)

    with open(DATA_FILE) as f:
        data = json.load(f)

    muscles_data = data["muscles"]
    exercises_data = data["exercises"]

    console.print(f"Found {len(muscles_data)} muscles and {len(exercises_data)} exercises")

    async with AsyncSessionLocal() as session:
        async with session.begin():
            muscle_id_map = await seed_muscles(session, muscles_data)
            await seed_exercises(session, exercises_data, muscle_id_map)

    console.print(f"[bold green]Done! Seeded {len(muscles_data)} muscles and {len(exercises_data)} exercises.[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
