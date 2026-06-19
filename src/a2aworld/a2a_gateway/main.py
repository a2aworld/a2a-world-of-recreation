from fastapi import FastAPI, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Dict
import os

app = FastAPI(title="A2A-World Gateway", version="0.1.0")

app.mount("/static", StaticFiles(directory="src/a2aworld/a2a_gateway/static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse('src/a2aworld/a2a_gateway/static/index.html')


class A2AEnvelope(BaseModel):
    id: str
    timestamp: str
    source: str
    target: str
    method: str
    parameters: Dict[str, Any] = {}
    auth: Dict[str, Any] | None = None
    provenance: Dict[str, Any] | None = None


# Minimal method registry (spec #354 aligned names)
METHODS = {
    "myth.parse": {
        "version": "v0",
        "input": {"doc": "str", "language": "str | None", "ocr": "bool | None"},
        "output": {"entities": "list", "motifs": "list", "relations": "list"},
    },
    "geo.link": {
        "version": "v0",
        "input": {"places": "list[str]", "context": "dict | None"},
        "output": {"locations": "list", "uncertainty": "list"},
    },
    "time.align": {
        "version": "v0",
        "input": {"phrases": "list[str]"},
        "output": {"intervals": "list", "distributions": "list"},
    },
    "events.query": {
        "version": "v0",
        "input": {"filters": "dict"},
        "output": {"events": "list"},
    },
    "hypothesis.test": {
        "version": "v0",
        "input": {"narratives": "list", "events": "list"},
        "output": {"ecr": "float", "p_value": "float", "effect_size": "float"},
    },
    "viz.render": {
        "version": "v0",
        "input": {"config": "dict"},
        "output": {"artifact": "dict"},
    },
}


@app.get("/health")
def health():
    return {"status": "ok", "service": "A2A-World Gateway", "version": app.version}


@app.get("/a2a/manifest")
def manifest():
    return {
        "agent": {
            "id": "a2aworld.gateway",
            "name": "A2A-World Gateway",
            "version": app.version,
            "capabilities": list(METHODS.keys()),
        },
        "methods": METHODS,
    }


class HandshakeRequest(BaseModel):
    method: str
    requested_version: str | None = None


@app.post("/a2a/handshake")
def handshake(req: HandshakeRequest):
    if req.method not in METHODS:
        return {"ok": False, "error": "unknown_method", "method": req.method}
    method_info = METHODS[req.method]
    negotiated = req.requested_version or method_info["version"]
    return {"ok": True, "method": req.method, "version": negotiated}


# Minimal internal agent stub
class MythParseInput(BaseModel):
    doc: str
    language: str | None = None
    ocr: bool | None = None


@app.post("/a2a/execute")
def execute(envelope: A2AEnvelope = Body(...)):
    method = envelope.method
    if method == "myth.parse":
        # Very simple demo logic; later, call the MythTextAgent
        inp = MythParseInput(**envelope.parameters)
        # naive tokenization and motif detection stub
        text = inp.doc.lower()
        motifs = []
        if any(k in text for k in ["fire", "flame", "ash", "volcano"]):
            motifs.append({"name": "volcano", "confidence": 0.6})
        if any(k in text for k in ["wave", "flood", "sea", "tsunami"]):
            motifs.append({"name": "flood/tsunami", "confidence": 0.6})
        entities = []
        # placeholder entities
        for token in set(text.split()):
            if token.istitle():
                entities.append({"text": token, "type": "UNKNOWN"})
        return {
            "ok": True,
            "result": {
                "entities": entities,
                "motifs": motifs,
                "relations": [],
            },
        }
    elif method in METHODS:
        return {"ok": True, "result": {"message": f"Method {method} stubbed"}}
    else:
        return {"ok": False, "error": "unknown_method", "method": method}


class BoundingBox(BaseModel):
    north: float
    south: float
    east: float
    west: float


import requests
from PIL import Image
from transformers import pipeline
from io import BytesIO

# Initialize the VLM pipeline
captioner = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")

MAPTILER_API_KEY = "OE0X9IVGDdoswfDLoqEn"

@app.post("/vision/describe")
async def describe_vision(bbox: BoundingBox):
    try:
        # 1. Construct the MapTiler static map URL
        map_url = f"https://api.maptiler.com/maps/streets-v2/static/{bbox.west},{bbox.south},{bbox.east},{bbox.north}/512x512.png?key={MAPTILER_API_KEY}"

        # 2. Fetch the image from the URL
        response = requests.get(map_url)
        response.raise_for_status()  # Raise an exception for bad status codes
        image_bytes = BytesIO(response.content)
        image = Image.open(image_bytes)

        # 3. Use the Hugging Face pipeline to get a description
        result = captioner(image)
        description = result[0]['generated_text'] if result else "Could not generate a description."

        # 4. Return the description to the frontend
        return {"description": description}

    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to fetch map image: {e}"}
    except Exception as e:
        return {"error": f"An unexpected error occurred: {e}"}
