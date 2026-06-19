import os
import httpx
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

PINATA_API_KEY = os.getenv("PINATA_API_KEY")
PINATA_SECRET_KEY = os.getenv("PINATA_SECRET_KEY")

class IPFSClient:
    """Client for Pinata IPFS API to store A2A-World visual evidence."""

    @classmethod
    async def pin_json(cls, data: Dict, name: str = "A2A_Observation") -> Optional[str]:
        """Pin a JSON object to IPFS."""
        if not PINATA_API_KEY or not PINATA_SECRET_KEY:
            logger.warning("PINATA_API_KEY not set. Skipping IPFS upload.")
            return None

        url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
        headers = {
            "pinata_api_key": PINATA_API_KEY,
            "pinata_secret_api_key": PINATA_SECRET_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "pinataOptions": {"cidVersion": 1},
            "pinataMetadata": {"name": name},
            "pinataContent": data
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=payload, timeout=10.0)
                response.raise_for_status()
                cid = response.json().get("IpfsHash")
                return f"ipfs://{cid}"
            except Exception as e:
                logger.error(f"Failed to pin JSON to IPFS: {e}")
                return None

    @classmethod
    async def pin_file(cls, file_bytes: bytes, filename: str, mime_type: str) -> Optional[str]:
        """Pin a file (like an image) to IPFS."""
        if not PINATA_API_KEY or not PINATA_SECRET_KEY:
            logger.warning("PINATA_API_KEY not set. Skipping IPFS upload.")
            return None

        url = "https://api.pinata.cloud/pinning/pinFileToIPFS"
        headers = {
            "pinata_api_key": PINATA_API_KEY,
            "pinata_secret_api_key": PINATA_SECRET_KEY
        }
        
        files = {
            'file': (filename, file_bytes, mime_type)
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, files=files, timeout=30.0)
                response.raise_for_status()
                cid = response.json().get("IpfsHash")
                return f"ipfs://{cid}"
            except Exception as e:
                logger.error(f"Failed to pin file to IPFS: {e}")
                return None
