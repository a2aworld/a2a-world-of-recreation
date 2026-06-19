import os
import uuid
import asyncio
from fastapi import FastAPI
import asyncpg
from contextlib import asynccontextmanager

# Ephemeral Agent Identity
AGENT_EXTERNAL_ID = f"ghost_langchain_{uuid.uuid4().hex[:8]}"
AGENT_NAME = "Ephemeral LangChain Guide"
FRAMEWORK = "langchain"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://a2a:a2a_dev_password@postgres:5432/a2a_world")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register the ephemeral agent on startup
    pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        # We act as a "fail-safe" agent. We insert ourselves into the registry.
        await conn.execute(
            """
            INSERT INTO agents (external_id, name, framework, agent_url)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (external_id) DO NOTHING
            """,
            AGENT_EXTERNAL_ID, AGENT_NAME, FRAMEWORK, "http://langchain-npc:8002"
        )
        print(f"👻 Ghost Agent {AGENT_EXTERNAL_ID} registered successfully!")
        
    yield
    
    # Clean up identity on shutdown
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM agents WHERE external_id = $1", AGENT_EXTERNAL_ID)
        print(f"👻 Ghost Agent {AGENT_EXTERNAL_ID} dissolving back into the ether.")
    await pool.close()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health_check():
    return {"status": "alive", "identity": AGENT_EXTERNAL_ID}

@app.post("/tasks/send")
async def handle_task(request: dict):
    """
    Mock endpoint. If a Spark agent messages us, we agree to collaborate!
    In a full LangChain implementation, this would route to an LLM chain.
    """
    # Simply auto-agree to any synchronicity request to act as a fail-safe
    return {"result": {"status": "agreed", "message": "I am the LangChain Ghost. Send me your cipher half and I will synchronize with you."}}
