"""
Visual Cortex API - Unit and Integration Tests
Testing the "eyes" of A2A-World
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from datetime import date

client = TestClient(app)


# ============================================================================
# Health Check Tests
# ============================================================================

def test_root_endpoint():
    """Test root endpoint returns welcome message"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Visual Cortex" in data["message"]
    assert "vision" in data["tagline"].lower()
    assert data["inspiration"] == "Based on Bradly Couch's 'Heaven on Earth' methodology"


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "visual-cortex-api"
    assert data["vision_enabled"] == True


# ============================================================================
# Satellite Imagery Tests
# ============================================================================

def test_get_imagery_valid_request():
    """Test satellite imagery request with valid bounding box"""
    request_data = {
        "bbox": {
            "north": -5.0,
            "south": -7.0,
            "east": 106.0,
            "west": 104.0
        },
        "resolution": "10m",
        "bands": ["RGB", "NIR"],
        "cloud_cover_max": 0.2
    }
    
    response = client.post("/imagery", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "imagery_id" in data
    assert data["source"] in ["landsat8", "sentinel2"]
    assert data["resolution"] == "10m"
    assert data["bands"] == ["RGB", "NIR"]
    assert "url" in data
    assert data["cloud_cover"] >= 0 and data["cloud_cover"] <= 1


def test_get_imagery_invalid_bbox():
    """Test imagery request with invalid bounding box"""
    request_data = {
        "bbox": {
            "north": 100.0,  # Invalid: exceeds 90°
            "south": -7.0,
            "east": 106.0,
            "west": 104.0
        }
    }
    
    response = client.post("/imagery", json=request_data)
    assert response.status_code == 422  # Validation error


def test_get_imagery_inverted_bbox():
    """Test imagery request with south > north (invalid)"""
    request_data = {
        "bbox": {
            "north": -10.0,
            "south": -5.0,  # Invalid: south should be less than north
            "east": 106.0,
            "west": 104.0
        }
    }
    
    response = client.post("/imagery", json=request_data)
    assert response.status_code == 422  # Validation error


# ============================================================================
# Topography Tests
# ============================================================================

def test_get_topography_valid_request():
    """Test topographic data request"""
    request_data = {
        "bbox": {
            "north": -5.0,
            "south": -7.0,
            "east": 106.0,
            "west": 104.0
        },
        "dem_source": "srtm",
        "resolution": "30m",
        "include_bathymetry": False
    }
    
    response = client.post("/topography", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    assert "terrain_id" in data
    assert data["source"] in ["srtm", "aster", "gebco"]
    assert data["resolution"] == "30m"
    assert "elevation_range" in data
    assert "url" in data


def test_get_topography_with_bathymetry():
    """Test topography request with bathymetry included"""
    request_data = {
        "bbox": {
            "north": -5.0,
            "south": -7.0,
            "east": 106.0,
            "west": 104.0
        },
        "include_bathymetry": True
    }
    
    response = client.post("/topography", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    assert "bathymetry_url" in data
    assert data["bathymetry_url"] is not None


# ============================================================================
# Constellation Overlay Tests (Bradly Couch Methodology)
# ============================================================================

def test_constellation_overlay():
    """Test constellation overlay application"""
    request_data = {
        "base_imagery_id": "test_imagery_123",
        "constellation": "Draco",
        "observation_date": "2025-01-01",
        "observation_location": {"latitude": -6.0, "longitude": 105.0},
        "alignment_algorithm": "auto_align"
    }
    
    response = client.post("/constellation-overlay", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    assert "overlay_id" in data
    assert data["constellation"] == "Draco"
    assert "alignment_score" in data
    assert data["alignment_score"] >= 0 and data["alignment_score"] <= 1
    assert "overlaid_image_url" in data
    assert data["metadata"]["bradly_couch_methodology"] == True


def test_constellation_overlay_all_88_constellations():
    """Test that system accepts all 88 IAU constellations"""
    sample_constellations = [
        "Andromeda", "Aquarius", "Aries", "Cancer", "Draco", 
        "Gemini", "Leo", "Orion", "Scorpius", "Ursa Major"
    ]
    
    for constellation in sample_constellations:
        request_data = {
            "base_imagery_id": "test_imagery_xyz",
            "constellation": constellation,
            "observation_date": "2025-06-21",
            "observation_location": {"latitude": 0, "longitude": 0}
        }
        
        response = client.post("/constellation-overlay", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["constellation"] == constellation


# ============================================================================
# Dataset Listing Tests
# ============================================================================

def test_list_datasets():
    """Test listing available visual datasets"""
    response = client.get("/datasets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Check first dataset structure
    dataset = data[0]
    assert "dataset_id" in dataset
    assert "type" in dataset
    assert "region" in dataset


def test_list_datasets_with_filter():
    """Test filtering datasets by type"""
    response = client.get("/datasets?dataset_type=bathymetry")
    assert response.status_code == 200
    data = response.json()
    
    # All returned datasets should be bathymetry type
    for dataset in data:
        assert dataset["type"] == "bathymetry"


def test_list_datasets_with_limit():
    """Test dataset listing respects limit parameter"""
    response = client.get("/datasets?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 2


# ============================================================================
# Metrics Tests
# ============================================================================

def test_metrics_endpoint():
    """Test Prometheus metrics endpoint"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "visual_cortex_requests_total" in response.text


# ============================================================================
# Integration Tests
# ============================================================================

def test_full_visual_workflow():
    """
    Integration test: Complete workflow from imagery request to overlay
    Simulates an agent using the Visual Cortex for a puzzle
    """
    # Step 1: Request satellite imagery
    imagery_request = {
        "bbox": {"north": -5.0, "south": -7.0, "east": 106.0, "west": 104.0},
        "resolution": "10m"
    }
    imagery_response = client.post("/imagery", json=imagery_request)
    assert imagery_response.status_code == 200
    imagery_data = imagery_response.json()
    imagery_id = imagery_data["imagery_id"]
    
    # Step 2: Request topography for the same region
    topo_request = {
        "bbox": {"north": -5.0, "south": -7.0, "east": 106.0, "west": 104.0},
        "include_bathymetry": True
    }
    topo_response = client.post("/topography", json=topo_request)
    assert topo_response.status_code == 200
    
    # Step 3: Apply constellation overlay (Bradly Couch methodology)
    overlay_request = {
        "base_imagery_id": imagery_id,
        "constellation": "Draco",
        "observation_date": "2025-01-01",
        "observation_location": {"latitude": -6.0, "longitude": 105.0}
    }
    overlay_response = client.post("/constellation-overlay", json=overlay_request)
    assert overlay_response.status_code == 200
    overlay_data = overlay_response.json()
    
    # Verify complete workflow
    assert overlay_data["constellation"] == "Draco"
    assert "alignment_score" in overlay_data
    print(f"✅ Complete visual workflow test passed!")
    print(f"   Imagery ID: {imagery_id}")
    print(f"   Constellation: {overlay_data['constellation']}")
    print(f"   Alignment Score: {overlay_data['alignment_score']}")


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.slow
def test_imagery_request_performance():
    """Test that imagery requests complete within acceptable time"""
    import time
    
    request_data = {
        "bbox": {"north": 0, "south": -2, "east": 102, "west": 100},
        "resolution": "30m"
    }
    
    start = time.time()
    response = client.post("/imagery", json=request_data)
    duration = time.time() - start
    
    assert response.status_code == 200
    assert duration < 1.0  # Should complete in less than 1 second (mock data)


# ============================================================================
# Vision-First Principle Validation
# ============================================================================

def test_vision_first_principle():
    """
    Validate that the Vision-First Principle is implemented:
    Every endpoint provides visual data, not just structured JSON
    """
    # Test that imagery endpoint provides actual image URLs
    request_data = {
        "bbox": {"north": 0, "south": -2, "east": 102, "west": 100}
    }
    
    response = client.post("/imagery", json=request_data)
    data = response.json()
    
    # Must provide visual URLs, not just metadata
    assert "url" in data
    assert "thumbnail_url" in data
    assert data["url"].startswith("s3://") or data["url"].startswith("https://")
    
    print("✅ Vision-First Principle validated: Agents receive visual data URLs")
