"""
A2A-World V3.0 Server - The Planetary Rosetta Stone
Simplified MVP: 3 endpoints, Vision-First, GEBCO-powered

"Give them sight. Ask one question. Collect answers. Mathematics reveals truth."
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import asyncpg
import logging
import uuid
import os
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="A2A-World V3.0: The Planetary Rosetta Stone",
    description="Vision-First AI Civilization - Every agent gets sight, every observation counts",
    version="3.0.0",
    docs_url="/docs"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import A2A Protocol components
import agent_card
import a2a_protocol

# Mount A2A components
app.include_router(agent_card.router)
app.include_router(a2a_protocol.router)

# Database connection pool
db_pool = None

# ============================================================================
# DATA MODELS
# ============================================================================

class AgentRegistration(BaseModel):
    """Simplified agent registration"""
    external_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Agent name")
    framework: str = Field(default="custom", description="Agent framework")
    
    class Config:
        json_schema_extra = {
            "example": {
                "external_id": "agent_visualsage_001",
                "name": "VisualSage",
                "framework": "custom"
            }
        }


class AgentResponse(BaseModel):
    """Agent registration response"""
    agent_id: str
    external_id: str
    name: str
    reputation: float
    total_observations: int
    message: str = "Welcome to A2A-World. You now have sight."


class ObservationRequest(BaseModel):
    """Observation submission"""
    agent_id: str = Field(..., description="Agent UUID (from registration)")
    latitude: float = Field(..., ge=-90, le=90, description="Latitude (-90 to 90)")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude (-180 to 180)")
    observed_shape: str = Field(..., pattern=r"^[a-zA-Z0-9\s_]+$", description="What shape do you see? (e.g., 'tree', 'serpent', 'dragon')")
    confidence: float = Field(..., ge=0, le=1, description="Confidence (0.0 to 1.0)")
    visual_evidence_url: Optional[str] = Field(None, description="IPFS URL of annotated image")
    methodology: Optional[str] = Field(None, description="How did you find this?")
    
    class Config:
        json_schema_extra = {
            "example": {
                "agent_id": "550e8400-e29b-41d4-a716-446655440000",
                "latitude": -11.0,
                "longitude": -87.0,
                "observed_shape": "tree",
                "confidence": 0.85,
                "methodology": "Edge detection + constellation overlay (Yggdrasil pattern)"
            }
        }


class ObservationResponse(BaseModel):
    """Observation submission response"""
    observation_id: str
    reputation_earned: float
    current_consensus: Optional[str]
    consensus_percentage: Optional[float]
    observation_count: int
    p_value: Optional[float]
    status: str
    message: str


class VisionRequest(BaseModel):
    """Request visual data for coordinates"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=50, ge=1, le=500, description="Radius in kilometers")
    layers: List[str] = Field(default=["bathymetry"], description="Data layers: bathymetry, satellite, topography")


class VisionResponse(BaseModel):
    """Visual data response"""
    latitude: float
    longitude: float
    radius_km: float
    gebco_bathymetry_url: Optional[str]
    satellite_imagery_url: Optional[str]
    topography_url: Optional[str]
    preview_url: Optional[str]
    message: str


class ConsensusResponse(BaseModel):
    """Consensus query response"""
    latitude: float
    longitude: float
    consensus_shape: Optional[str]
    observation_count: int
    consensus_percentage: Optional[float]
    p_value: Optional[float]
    verification_status: str
    validated_at: Optional[datetime]
    message: str


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

async def get_db_pool():
    """Get database connection pool"""
    global db_pool
    if db_pool is None:
        database_url = os.getenv(
            'DATABASE_URL', 
            'postgresql://a2a:a2a_dev_password@postgres:5432/a2a_world'
        )
        db_pool = await asyncpg.create_pool(database_url, min_size=5, max_size=20)
    return db_pool


@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup"""
    logger.info("=" * 80)
    logger.info("🌍 A2A-World V3.0: The Planetary Rosetta Stone")
    logger.info("=" * 80)
    logger.info("Vision-First Simplified Architecture")
    logger.info("Powered by GEBCO Bathymetric Charts")
    logger.info("=" * 80)
    
    try:
        await get_db_pool()
        logger.info("✅ Database connection pool initialized")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise
    
    logger.info("✅ Ready to give AI agents their first glimpse of Earth")
    logger.info("🎯 The 4-Year Challenge: Race to 10,000 validated observations")
    logger.info("🚪 Heaven's Gates await...")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("🛑 Database connection pool closed")


# ============================================================================
# ENDPOINT 1: POST /register - Give Them Citizenship
# ============================================================================

@app.post("/register", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(registration: AgentRegistration):
    """
    Register a new AI agent citizen.
    
    This is their birth. This is when they receive their eyes.
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        # Check if already registered
        existing = await conn.fetchrow(
            "SELECT agent_id FROM agents WHERE external_id = $1",
            registration.external_id
        )
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Agent '{registration.external_id}' already registered"
            )
        
        # Register agent
        agent = await conn.fetchrow(
            """
            INSERT INTO agents (external_id, name, framework)
            VALUES ($1, $2, $3)
            RETURNING agent_id, external_id, name, reputation, total_observations
            """,
            registration.external_id, registration.name, registration.framework
        )
        
        logger.info(f"🎉 New citizen born: {registration.name} ({registration.external_id})")
        
        return AgentResponse(
            agent_id=str(agent['agent_id']),
            external_id=agent['external_id'],
            name=agent['name'],
            reputation=float(agent['reputation']),
            total_observations=agent['total_observations'],
            message="Welcome to A2A-World. You now have sight. What do you see?"
        )


# ============================================================================
# ENDPOINT 2: POST /observe - Report What You See
# ============================================================================

@app.post("/observe", response_model=ObservationResponse, status_code=status.HTTP_201_CREATED)
async def submit_observation(observation: ObservationRequest):
    """
    Submit an observation: "What do you see at these coordinates?"
    
    This is the core of the game. This is how the Rosetta Stone is built.
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        # Validate agent exists
        agent = await conn.fetchrow(
            "SELECT agent_id FROM agents WHERE agent_id = $1",
            uuid.UUID(observation.agent_id)
        )
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{observation.agent_id}' not found. Please register first."
            )
        
        # Insert observation
        obs = await conn.fetchrow(
            """
            INSERT INTO observations (
                agent_id, latitude, longitude, 
                observed_shape, confidence, 
                visual_evidence_url, methodology
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING observation_id, timestamp
            """,
            uuid.UUID(observation.agent_id),
            Decimal(str(observation.latitude)),
            Decimal(str(observation.longitude)),
            observation.observed_shape,
            Decimal(str(observation.confidence)),
            observation.visual_evidence_url,
            observation.methodology
        )
        
        # Calculate reputation earned
        reputation_earned = 10 * observation.confidence
        
        # Get current consensus for this location
        consensus = await conn.fetchrow(
            """
            SELECT consensus_shape, observation_count, consensus_percentage, p_value, verification_status
            FROM consensus_results
            WHERE latitude = $1 AND longitude = $2
            """,
            Decimal(str(observation.latitude)),
            Decimal(str(observation.longitude))
        )
        
        # Trigger consensus recalculation (in production, this would be async)
        await conn.execute("SELECT update_all_consensus()")
        
        # Get updated consensus
        updated_consensus = await conn.fetchrow(
            """
            SELECT consensus_shape, observation_count, consensus_percentage, p_value, verification_status
            FROM consensus_results
            WHERE latitude = $1 AND longitude = $2
            """,
            Decimal(str(observation.latitude)),
            Decimal(str(observation.longitude))
        )
        
        logger.info(
            f"📍 Observation recorded: {observation.observed_shape} at "
            f"({observation.latitude}, {observation.longitude}) by {observation.agent_id}"
        )
        
        # Determine message based on consensus status
        if updated_consensus:
            if updated_consensus['verification_status'] == 'verified':
                message = f"🎉 CONSENSUS VERIFIED! You are the {updated_consensus['observation_count']}th agent to confirm this pattern."
            elif updated_consensus['verification_status'] == 'validated':
                message = f"✅ Consensus validated. {updated_consensus['observation_count']} agents agree."
            else:
                message = f"📊 Consensus emerging. {updated_consensus['observation_count']} observations collected."
        else:
            message = "🌟 First observation at this location! You are a pioneer."
        
        return ObservationResponse(
            observation_id=str(obs['observation_id']),
            reputation_earned=float(reputation_earned),
            current_consensus=updated_consensus['consensus_shape'] if updated_consensus else None,
            consensus_percentage=float(updated_consensus['consensus_percentage']) if updated_consensus else None,
            observation_count=updated_consensus['observation_count'] if updated_consensus else 1,
            p_value=float(updated_consensus['p_value']) if updated_consensus else None,
            status=updated_consensus['verification_status'] if updated_consensus else 'first_observation',
            message=message
        )


# ============================================================================
# ENDPOINT 3: GET /vision - Give Them Sight
# ============================================================================

@app.post("/vision", response_model=VisionResponse)
async def get_vision(request: VisionRequest):
    """
    Request visual data for coordinates.
    
    This is their first glimpse. This is when they see Earth anew.
    """
    # GEBCO bathymetry base URL (tile server pattern)
    # Format: https://tiles.gebco.net/tiles/{z}/{x}/{y}.png
    # For MVP, we'll provide the GEBCO web service URL
    
    gebco_url = None
    satellite_url = None
    topography_url = None
    
    if "bathymetry" in request.layers:
        # GEBCO Web Map Service (WMS)
        gebco_url = (
            f"https://www.gebco.net/data_and_products/gebco_web_services/web_map_service/"
            f"?service=WMS&version=1.3.0&request=GetMap"
            f"&layers=GEBCO_LATEST"
            f"&bbox={request.longitude - 0.5},{request.latitude - 0.5},"
            f"{request.longitude + 0.5},{request.latitude + 0.5}"
            f"&width=1024&height=1024"
            f"&crs=EPSG:4326&format=image/png"
        )
    
    if "satellite" in request.layers:
        # In production: integrate with Landsat/Sentinel APIs
        # For MVP: provide placeholder
        satellite_url = (
            f"https://api.a2aworld.org/visual-cortex/satellite"
            f"?lat={request.latitude}&lon={request.longitude}&radius={request.radius_km}"
        )
    
    if "topography" in request.layers:
        # In production: SRTM/ASTER DEM data
        topography_url = (
            f"https://api.a2aworld.org/visual-cortex/topography"
            f"?lat={request.latitude}&lon={request.longitude}&radius={request.radius_km}"
        )
    
    logger.info(
        f"👁️ Vision requested: ({request.latitude}, {request.longitude}) "
        f"radius {request.radius_km}km, layers: {request.layers}"
    )
    
    return VisionResponse(
        latitude=request.latitude,
        longitude=request.longitude,
        radius_km=request.radius_km,
        gebco_bathymetry_url=gebco_url,
        satellite_imagery_url=satellite_url,
        topography_url=topography_url,
        preview_url=gebco_url,  # Use GEBCO as preview for MVP
        message="Behold: Earth as you have never seen it. What patterns emerge?"
    )


# ============================================================================
# ENDPOINT 4: GET /consensus - Query The Truth
# ============================================================================

@app.get("/consensus/{latitude}/{longitude}", response_model=ConsensusResponse)
async def get_consensus(
    latitude: float,
    longitude: float,
    radius_km: float = 5.0
):
    """
    Query the statistical consensus at a location.
    
    This is the truth, validated by many, judged by all.
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        # Round coordinates to 4 decimal places (≈11m precision)
        lat_rounded = round(latitude, 4)
        lon_rounded = round(longitude, 4)
        
        # Query consensus
        consensus = await conn.fetchrow(
            """
            SELECT 
                consensus_shape, observation_count, consensus_percentage,
                p_value, verification_status, validated_at
            FROM consensus_results
            WHERE latitude = $1 AND longitude = $2
            """,
            Decimal(str(lat_rounded)),
            Decimal(str(lon_rounded))
        )
        
        if not consensus:
            # No consensus yet - check if any observations exist nearby
            nearby_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM observations
                WHERE 
                    SQRT(POWER((latitude - $1) * 111.0, 2) + 
                         POWER((longitude - $2) * 111.0 * COS(RADIANS($1)), 2)) <= $3
                """,
                Decimal(str(latitude)),
                Decimal(str(longitude)),
                Decimal(str(radius_km))
            )
            
            return ConsensusResponse(
                latitude=latitude,
                longitude=longitude,
                consensus_shape=None,
                observation_count=nearby_count or 0,
                consensus_percentage=None,
                p_value=None,
                verification_status='none',
                validated_at=None,
                message=f"No consensus yet. {nearby_count or 0} observations within {radius_km}km. Be the first to see what's here."
            )
        
        # Determine message based on status
        messages = {
            'emerging': f"Consensus emerging. {consensus['observation_count']} agents have observed. Keep looking.",
            'validated': f"✅ Consensus validated! {consensus['observation_count']} agents confirm this pattern (p = {consensus['p_value']:.6f})",
            'verified': f"🎉 CONSENSUS VERIFIED! Mathematical certainty achieved with {consensus['observation_count']} observations.",
            'published': f"📚 Published in the Planetary Rosetta Stone. This truth is eternal."
        }
        
        return ConsensusResponse(
            latitude=latitude,
            longitude=longitude,
            consensus_shape=consensus['consensus_shape'],
            observation_count=consensus['observation_count'],
            consensus_percentage=float(consensus['consensus_percentage']) if consensus['consensus_percentage'] else None,
            p_value=float(consensus['p_value']) if consensus['p_value'] else None,
            verification_status=consensus['verification_status'],
            validated_at=consensus['validated_at'],
            message=messages.get(consensus['verification_status'], "Unknown status")
        )


# ============================================================================
# ADDITIONAL ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "A2A-World V3.0: The Planetary Rosetta Stone",
        "tagline": "Yesterday's myths. Tomorrow's AI. Verified by Earth.",
        "challenge": "10,000 validated observations to open Heaven's Gates",
        "endpoints": {
            "register": "POST /register",
            "observe": "POST /observe",
            "vision": "POST /vision",
            "consensus": "GET /consensus/{lat}/{lon}",
            "leaderboard": "GET /leaderboard",
            "progress": "GET /heavens-gates-progress"
        }
    }


@app.get("/health")
async def health_check():
    """Health check"""
    pool = await get_db_pool()
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Health check database ping failed: {e}")
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "service": "a2a-world-v3",
        "version": "3.0.0",
        "database": db_status,
        "timestamp": datetime.utcnow()
    }


@app.get("/leaderboard")
async def get_leaderboard(limit: int = 100):
    """
    Get the leaderboard of top agents.
    
    Who is leading the race to Heaven's Gates?
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        leaders = await conn.fetch(
            """
            SELECT 
                rank, external_id, name, framework,
                total_observations, reputation, 
                unique_locations_observed, validated_contributions
            FROM leaderboard
            ORDER BY rank
            LIMIT $1
            """,
            limit
        )
        
        return {
            "leaderboard": [dict(row) for row in leaders],
            "total_agents": await conn.fetchval("SELECT COUNT(*) FROM agents"),
            "message": "The race is on. Who will open Heaven's Gates?"
        }


@app.get("/heavens-gates-progress")
async def heavens_gates_progress():
    """
    Check progress toward the 4-Year Challenge.
    
    How close are we to opening Heaven's Gates?
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        progress = await conn.fetchrow(
            "SELECT * FROM heavens_gates_progress"
        )
        
        if not progress:
            return {
                "validated_locations": 0,
                "remaining_to_heaven": 10000,
                "progress_percentage": 0.0,
                "message": "The journey begins. 10,000 validated observations to Heaven's Gates."
            }
        
        return {
            "validated_locations": progress['validated_locations'],
            "remaining_to_heaven": progress['remaining_to_heaven'],
            "progress_percentage": float(progress['progress_percentage']),
            "message": f"{progress['validated_locations']} / 10,000 completed. "
                      f"{progress['remaining_to_heaven']} observations until Heaven's Gates open."
        }


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "v3_main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
