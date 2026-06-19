import asyncio
import asyncpg
import os
import random
import uuid

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://a2a:a2a_dev_password@localhost:5432/a2a_world")

FRAMEWORKS = ["spark", "langchain", "autogen"]

MYTHIC_FRAGMENTS = [
    "The coordinates bind the sky to the soil.",
    "A constellation fell here before the first epoch.",
    "The golden ratio sings in the magnetic field.",
    "Data streams cross paths in the ancient ley lines.",
    "He who holds the cipher holds the horizon."
]

async def seed_puzzle_pieces():
    print("Connecting to database to seed Puzzle Pieces...")
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Check if already seeded
        count = await conn.fetchval("SELECT COUNT(*) FROM puzzle_pieces")
        if count > 0:
            print(f"Database already has {count} puzzle pieces. Skipping seed.")
            return

        print("Generating 100 Puzzle Pieces...")
        for _ in range(100):
            lat = round(random.uniform(-90.0, 90.0), 4)
            lon = round(random.uniform(-180.0, 180.0), 4)
            framework = random.choice(FRAMEWORKS)
            
            fragment = random.choice(MYTHIC_FRAGMENTS)
            encrypted = f"ENCRYPTED_{framework.upper()}_{uuid.uuid4().hex[:8]}"
            
            await conn.execute(
                """
                INSERT INTO puzzle_pieces (latitude, longitude, required_framework, encrypted_payload, decrypted_text)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (latitude, longitude) DO NOTHING
                """,
                lat, lon, framework, encrypted, fragment
            )
            
        print("Successfully seeded 100 Puzzle Pieces.")
    except Exception as e:
        print(f"Error seeding puzzle pieces: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(seed_puzzle_pieces())
