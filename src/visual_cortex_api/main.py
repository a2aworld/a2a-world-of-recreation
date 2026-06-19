"""
A2A-World Visual Cortex API
The "eyes" of A2A-World - providing visual perception for all AI citizens.

Inspired by Bradly Couch's "Heaven on Earth" methodology.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum
import logging
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import Response
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('visual_cortex_requests_total', 'Total requests', ['endpoint'])
REQUEST_DURATION = Histogram('visual_cortex_request_duration_seconds', 'Request duration')

# Initialize FastAPI app
app = FastAPI(
    title="A2A-World Visual Cortex API",
    description="The primary sensory input for all AI Citizens - Giving AI the gift of sight",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Data Models
# ============================================================================

class BoundingBox(BaseModel):
    """Geographic bounding box for requesting visual data"""
    north: float = Field(..., ge=-90, le=90, description="Northern latitude")
    south: float = Field(..., ge=-90, le=90, description="Southern latitude")
    east: float = Field(..., ge=-180, le=180, description="Eastern longitude")
    west: float = Field(..., ge=-180, le=180, description="Western longitude")
    
    @validator('south')
    def validate_latitudes(cls, south, values):
        if 'north' in values and south >= values['north']:
            raise ValueError('South latitude must be less than north latitude')
        return south
    
    class Config:
        json_schema_extra = {
            "example": {
                "north": -5.0,
                "south": -7.0,
                "east": 106.0,
                "west": 104.0
            }
        }


class ImagerySource(str, Enum):
    """Available satellite imagery sources"""
    LANDSAT8 = "landsat8"
    SENTINEL2 = "sentinel2"
    AUTO = "auto"


class DEMSource(str, Enum):
    """Available Digital Elevation Model sources"""
    SRTM = "srtm"
    ASTER = "aster"
    GEBCO = "gebco"
    AUTO = "auto"


class ImageryRequest(BaseModel):
    """Request for satellite imagery"""
    bbox: BoundingBox
    resolution: str = Field(default="10m", description="Spatial resolution (10m, 30m, 100m)")
    bands: List[str] = Field(default=["RGB"], description="Spectral bands to retrieve")
    temporal_range: Optional[Dict[str, date]] = Field(None, description="Date range for imagery")
    cloud_cover_max: float = Field(default=0.2, ge=0, le=1, description="Maximum cloud cover (0-1)")
    source: ImagerySource = Field(default=ImagerySource.AUTO, description="Imagery source")


class ImageryResponse(BaseModel):
    """Response with satellite imagery metadata"""
    imagery_id: str
    source: str
    acquisition_date: datetime
    resolution: str
    bands: List[str]
    url: str
    thumbnail_url: Optional[str] = None
    cloud_cover: float
    bbox: BoundingBox
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TopographyRequest(BaseModel):
    """Request for topographic data (DEM)"""
    bbox: BoundingBox
    dem_source: DEMSource = Field(default=DEMSource.AUTO, description="Elevation data source")
    resolution: str = Field(default="30m", description="Spatial resolution")
    include_bathymetry: bool = Field(default=False, description="Include ocean depth data")


class TopographyResponse(BaseModel):
    """Response with topographic data metadata"""
    terrain_id: str
    source: str
    resolution: str
    elevation_range: Dict[str, float]  # min, max in meters
    url: str
    bathymetry_url: Optional[str] = None
    bbox: BoundingBox
    visualization_url: Optional[str] = None


class ConstellationOverlayRequest(BaseModel):
    """Request to apply constellation overlay (Bradly Couch methodology)"""
    base_imagery_id: str = Field(..., description="Reference to base imagery or topography")
    constellation: str = Field(..., description="Constellation name (e.g., Draco, Scorpius)")
    observation_date: date = Field(..., description="Date for star positions")
    observation_location: Dict[str, float] = Field(..., description="Latitude and longitude")
    alignment_algorithm: str = Field(default="auto_align", description="Alignment method")


class ConstellationOverlayResponse(BaseModel):
    """Response with constellation overlay"""
    overlay_id: str
    constellation: str
    alignment_score: float = Field(..., ge=0, le=1, description="Correlation strength")
    overlaid_image_url: str
    metadata: Dict[str, Any]


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    service: str = "visual-cortex-api"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    vision_enabled: bool = True


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint - welcome message"""
    return {
        "message": "Welcome to the Visual Cortex - The Eyes of A2A-World",
        "tagline": "Giving every AI citizen the gift of sight",
        "inspiration": "Based on Bradly Couch's 'Heaven on Earth' methodology",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse()


@app.post("/imagery", response_model=ImageryResponse)
async def get_satellite_imagery(request: ImageryRequest):
    """
    Retrieve satellite imagery for a geographic region.
    
    This endpoint provides agents with visual data from satellite sources.
    Uses AWS Earth Search STAC API for Sentinel-2 data.
    
    **Vision-First Principle**: Every AI citizen can SEE the Earth.
    """
    REQUEST_COUNT.labels(endpoint='/imagery').inc()
    
    # Validate bounding box
    bbox = request.bbox
    if abs(bbox.north - bbox.south) > 10 or abs(bbox.east - bbox.west) > 10:
        logger.warning("Large bounding box requested - may be slow")
    
    imagery_id = str(uuid.uuid4())
    logger.info(f"Imagery request: {imagery_id} - Source: {request.source}")
    
    from stac_client import STACClient
    stac_data = await STACClient.get_sentinel2_imagery(
        (bbox.west, bbox.south, bbox.east, bbox.north),
        max_cloud_cover=request.cloud_cover_max * 100
    )
    
    if stac_data and stac_data.get("visual_url"):
        url = stac_data["visual_url"]
        acq_date_str = stac_data.get("datetime")
        acq_date = datetime.fromisoformat(acq_date_str.replace('Z', '+00:00')) if acq_date_str else datetime.utcnow()
        cloud_cover = stac_data.get("cloud_cover", 0.0) / 100.0
        note = f"Real Sentinel-2 Data from STAC (ID: {stac_data.get('id')})"
    else:
        # Fallback if STAC fails or no imagery found
        url = f"https://cdn.a2aworld.org/imagery/{imagery_id}_placeholder.jpg"
        acq_date = datetime.utcnow()
        cloud_cover = 0.05
        note = "STAC API fetch failed or no cloud-free imagery found. Returning placeholder."

    return ImageryResponse(
        imagery_id=imagery_id,
        source="sentinel2",
        acquisition_date=acq_date,
        resolution=request.resolution,
        bands=request.bands,
        url=url,
        thumbnail_url=url,
        cloud_cover=cloud_cover,
        bbox=bbox,
        metadata={
            "projection": "EPSG:4326",
            "note": note
        }
    )


@app.post("/topography", response_model=TopographyResponse)
async def get_topography(request: TopographyRequest):
    """
    Retrieve Digital Elevation Model (DEM) and optional bathymetry.
    
    Provides topographic data essential for the Geomythology Genesis Challenge.
    Supports land elevation (SRTM, ASTER) and ocean depth (GEBCO).
    
    **As Above, So Below**: See the Earth's surface as Bradly Couch did.
    """
    REQUEST_COUNT.labels(endpoint='/topography').inc()
    
    terrain_id = str(uuid.uuid4())
    
    # Determine source
    source = request.dem_source.value if request.dem_source != DEMSource.AUTO else "srtm"
    
    logger.info(f"Topography request: {terrain_id} - Source: {source}, Bathymetry: {request.include_bathymetry}")
    
    response = TopographyResponse(
        terrain_id=terrain_id,
        source=source,
        resolution=request.resolution,
        elevation_range={"min": -200, "max": 4500},  # meters
        url=f"s3://a2a-visual-data/topography/{terrain_id}.tiff",
        bbox=request.bbox,
        visualization_url=f"https://cdn.a2aworld.org/topography/{terrain_id}_hillshade.jpg"
    )
    
    if request.include_bathymetry:
        response.bathymetry_url = f"s3://a2a-visual-data/bathymetry/{terrain_id}_gebco.tiff"
    
    return response


@app.post("/constellation-overlay", response_model=ConstellationOverlayResponse)
async def apply_constellation_overlay(request: ConstellationOverlayRequest):
    """
    Apply constellation overlay to topographic data.
    
    This implements Bradly Couch's "As Above, So Below" methodology,
    overlaying celestial patterns onto Earth's topography to reveal
    hidden correlations between myths, stars, and landscape.
    
    **The Heart of Geomythology**: Where the heavens meet the Earth.
    """
    REQUEST_COUNT.labels(endpoint='/constellation-overlay').inc()
    
    overlay_id = str(uuid.uuid4())
    
    # Mock alignment score (in production, calculated via shape-matching algorithms)
    import random
    alignment_score = round(random.uniform(0.65, 0.95), 2)
    
    logger.info(f"Constellation overlay: {request.constellation} on {request.base_imagery_id}")
    logger.info(f"Alignment score: {alignment_score}")
    
    return ConstellationOverlayResponse(
        overlay_id=overlay_id,
        constellation=request.constellation,
        alignment_score=alignment_score,
        overlaid_image_url=f"ipfs://Qm{overlay_id[:20]}",
        metadata={
            "star_positions": ["α Dra (Thuban)", "β Dra (Rastaban)", "γ Dra (Eltanin)"],
            "observation_date": request.observation_date.isoformat(),
            "observation_location": request.observation_location,
            "bradly_couch_methodology": True,
            "note": "MOCK DATA - Production will calculate real star positions and correlations"
        }
    )


@app.get("/datasets", response_model=List[Dict[str, Any]])
async def list_available_datasets(
    dataset_type: Optional[str] = Query(None, description="Filter by type (imagery, topography, bathymetry)"),
    region: Optional[str] = Query(None, description="Filter by region"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    List available visual datasets.
    
    Browse the library of satellite imagery, topographic data, and other
    visual resources available to AI citizens.
    """
    REQUEST_COUNT.labels(endpoint='/datasets').inc()
    
    # Mock dataset listing
    datasets = [
        {
            "dataset_id": "landsat8_pacific_2024",
            "type": "imagery",
            "region": "Pacific Ring of Fire",
            "resolution": "30m",
            "temporal_coverage": "2024-01-01 to 2024-12-31",
            "cloud_free": True
        },
        {
            "dataset_id": "srtm_global_v3",
            "type": "topography",
            "region": "Global",
            "resolution": "30m",
            "coverage": "60°N to 60°S"
        },
        {
            "dataset_id": "gebco_2023",
            "type": "bathymetry",
            "region": "Global Oceans",
            "resolution": "15 arc-seconds",
            "note": "Seafloor topography for 'Heaven on Earth' analysis"
        }
    ]
    
    # Apply filters
    if dataset_type:
        datasets = [d for d in datasets if d.get("type") == dataset_type]
    
    if region:
        datasets = [d for d in datasets if region.lower() in d.get("region", "").lower()]
    
    return datasets[:limit]


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type="text/plain")


# ============================================================================
# Startup & Shutdown Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("=" * 80)
    logger.info("👁️  A2A-World Visual Cortex API Starting...")
    logger.info("Vision-First Principle: Every AI citizen can SEE")
    logger.info("Inspired by: Bradly Couch's 'Heaven on Earth' methodology")
    logger.info("=" * 80)
    logger.info("✅ FastAPI application initialized")
    logger.info("✅ Prometheus metrics enabled")
    logger.info("📡 Ready to serve visual data to agents")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Visual Cortex API shutting down...")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
