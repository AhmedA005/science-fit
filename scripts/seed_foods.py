"""
Seed script: import USDA FoodData Central data into PostgreSQL.

Downloads Foundation Foods + SR Legacy from the USDA API (free, no key needed
for DEMO_KEY tier) and imports a curated subset of common foods.

All values are stored per 100g — MealPlanItem.quantity_g scales them at query time.

Usage:
    python scripts/seed_foods.py

Raw downloads are cached in data/usda_raw/ so re-runs don't re-download.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from rich.console import Console
from rich.progress import track
from sqlalchemy import text

from src.database import AsyncSessionLocal

console = Console()

USDA_API_BASE = "https://api.nal.usda.gov/fdc/v1"
# Free DEMO_KEY: 30 req/hr. Replace with a free personal key from
# https://fdc.nal.usda.gov/api-key-signup.html for higher limits.
USDA_API_KEY = "DEMO_KEY"

CACHE_DIR = Path(__file__).parent.parent / "data" / "usda_raw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# USDA nutrient IDs we care about
NUTRIENT_IDS = {
    1008: "calories",
    1003: "protein_g",
    1005: "carbohydrate_g",
    1004: "fat_g",
    1079: "fiber_g",
}

# Food categories to include (practical, whole foods)
INCLUDED_CATEGORIES = {
    "Beef Products",
    "Poultry Products",
    "Finfish and Shellfish Products",
    "Pork Products",
    "Lamb, Veal, and Game Products",
    "Dairy and Egg Products",
    "Legumes and Legume Products",
    "Nut and Seed Products",
    "Cereal Grains and Pasta",
    "Vegetables and Vegetable Products",
    "Fruits and Fruit Juices",
    "Fats and Oils",
    "Breakfast Cereals",
    "Baked Products",
}

# Keywords that indicate unhelpful entries
SKIP_KEYWORDS = [
    "baby food", "infant", "NFS", "not further specified",
    "frozen meal", "TV dinner", "NS as to",
]


def fetch_page(page: int, page_size: int = 200) -> list[dict]:
    """Fetch one page of foods from USDA API, using local cache when available."""
    cache_file = CACHE_DIR / f"usda_page_{page}.json"

    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    url = f"{USDA_API_BASE}/foods/list"
    params = {
        "dataType": ["Foundation", "SR Legacy"],
        "pageSize": page_size,
        "pageNumber": page,
        "api_key": USDA_API_KEY,
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    with open(cache_file, "w") as f:
        json.dump(data, f)

    return data


def extract_nutrients(food: dict) -> dict:
    """Pull the macro values we need from a USDA food entry."""
    result = {
        "calories": 0.0,
        "protein_g": 0.0,
        "carbohydrate_g": 0.0,
        "fat_g": 0.0,
        "fiber_g": None,
    }
    for n in food.get("foodNutrients", []):
        nid = n.get("nutrientId") or n.get("number")
        if nid and int(nid) in NUTRIENT_IDS:
            field = NUTRIENT_IDS[int(nid)]
            result[field] = float(n.get("value") or 0)
    return result


def is_useful(food: dict) -> bool:
    """Return True if this food is worth importing."""
    category = food.get("foodCategory", "")
    name = (food.get("description") or "").lower()

    if category not in INCLUDED_CATEGORIES:
        return False
    if any(kw.lower() in name for kw in SKIP_KEYWORDS):
        return False
    return True


async def insert_foods(foods: list[dict]) -> int:
    """Bulk-insert foods. Returns count of rows actually inserted."""
    inserted = 0
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for food in track(foods, description="Inserting foods..."):
                nutrients = extract_nutrients(food)
                result = await session.execute(
                    text("""
                        INSERT INTO foods (
                            fdc_id, name, serving_size_g, serving_description,
                            calories, protein_g, carbohydrate_g, fat_g, fiber_g, category
                        ) VALUES (
                            :fdc_id, :name, 100.0, '100g',
                            :calories, :protein_g, :carbohydrate_g, :fat_g, :fiber_g, :category
                        )
                        ON CONFLICT (fdc_id) DO NOTHING
                        RETURNING id
                    """),
                    {
                        "fdc_id": str(food.get("fdcId", "")),
                        "name": (food.get("description") or "")[:200],
                        "calories": nutrients["calories"],
                        "protein_g": nutrients["protein_g"],
                        "carbohydrate_g": nutrients["carbohydrate_g"],
                        "fat_g": nutrients["fat_g"],
                        "fiber_g": nutrients["fiber_g"],
                        "category": food.get("foodCategory"),
                    },
                )
                if result.fetchone():
                    inserted += 1
    return inserted


async def main() -> None:
    console.print("[bold blue]Science-Fit USDA Food Seeder[/bold blue]")
    console.print(f"API: {USDA_API_BASE}  |  Cache: {CACHE_DIR}")
    console.print("Using DEMO_KEY (30 req/hr). Replace USDA_API_KEY for higher limits.\n")

    all_foods: list[dict] = []
    page = 1
    MAX_PAGES = 15  # ~3000 raw items before filtering

    while page <= MAX_PAGES:
        data = fetch_page(page)
        if not data:
            break
        all_foods.extend(data)
        console.print(f"  Page {page}: {len(data)} items  (total: {len(all_foods)})")
        if len(data) < 200:
            break
        page += 1

    console.print(f"\nTotal fetched : {len(all_foods)}")

    useful = [f for f in all_foods if is_useful(f)]
    console.print(f"After filter  : {len(useful)} useful foods\n")

    inserted = await insert_foods(useful)
    console.print(f"\n[bold green]Done! Inserted {inserted} foods into the database.[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
