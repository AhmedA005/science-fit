"""Quick smoke test for the training engine against the test user."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from src.database import AsyncSessionLocal
from src.services import TrainingEngine


async def main():
    async with AsyncSessionLocal() as session:
        engine = TrainingEngine(session)
        for user_id in [1, 2, 3]:
            try:
                ctx = await engine.build_context(user_id=user_id, weeks_of_history=4)
                text = engine.format_context_for_llm(ctx)
                Path("test_output.txt").write_text(text, encoding="utf-8")
                print("SUCCESS: Context written to test_output.txt")
                break
            except ValueError:
                continue

asyncio.run(main())
