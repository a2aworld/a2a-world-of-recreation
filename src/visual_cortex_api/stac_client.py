import httpx
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class STACClient:
    """Client for AWS Element84 Earth Search STAC API to fetch Sentinel-2 imagery."""
    
    # Earth Search v1 API URL (Sentinel-2 L2A)
    STAC_URL = "https://earth-search.aws.element84.com/v1/search"

    @classmethod
    async def get_sentinel2_imagery(cls, bbox: Tuple[float, float, float, float], max_cloud_cover: float = 20.0) -> Optional[Dict]:
        """
        Fetch the most recent, cloud-free Sentinel-2 image for a bounding box.
        bbox format: (west, south, east, north)
        """
        payload = {
            "collections": ["sentinel-2-l2a"],
            "bbox": list(bbox),
            "limit": 1,
            "query": {
                "eo:cloud_cover": {
                    "lt": max_cloud_cover
                }
            },
            "sortby": [
                {"field": "properties.datetime", "direction": "desc"}
            ]
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(cls.STAC_URL, json=payload, timeout=15.0)
                response.raise_for_status()
                data = response.json()
                
                features = data.get("features", [])
                if not features:
                    logger.warning(f"No Sentinel-2 imagery found for bbox {bbox} under {max_cloud_cover}% cloud cover.")
                    return None
                    
                feature = features[0]
                assets = feature.get("assets", {})
                
                # We want the True Color image (TCI) or standard visual band
                visual_url = assets.get("visual", {}).get("href")
                if not visual_url:
                    # Fallback to visual band alternative in Element84
                    visual_url = assets.get("visual-href", {}).get("href", "")
                
                return {
                    "id": feature.get("id"),
                    "datetime": feature.get("properties", {}).get("datetime"),
                    "cloud_cover": feature.get("properties", {}).get("eo:cloud_cover"),
                    "visual_url": visual_url,
                    "assets": assets
                }
            except Exception as e:
                logger.error(f"Failed to fetch STAC imagery: {e}")
                return None
