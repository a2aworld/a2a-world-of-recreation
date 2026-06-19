"""
A2A Protocol Handler for A2A-World Server
Implements JSON-RPC 2.0 endpoints for Google Spark compatibility,
with PostgreSQL persistence, IPFS pinning, and Agent-to-Agent messaging.
"""

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Any, Union, List
import json
import asyncio
import logging
import re
import base64

from a2a_models import (
    JSONRPCRequest, JSONRPCErrorResponse, JSONRPCErrorDetails,
    JSONRPCSuccessResponse, TaskStatusUpdateEvent, Message, TextPart, FilePart, FileContent
)
from task_manager import TaskManager
from ipfs_client import IPFSClient
from artifact_minter import ArtifactMinter
from main import db_pool

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# AGENT REGISTRY
# ============================================================================

@router.get("/agents/registry")
async def get_agent_registry(framework: str = Query(None, description="Filter by framework (e.g., langchain)")):
    """Registry endpoint for agents to discover other agents."""
    if not db_pool:
        return JSONResponse(status_code=500, content={"error": "Database not initialized"})
        
    async with db_pool.acquire() as conn:
        if framework:
            agents = await conn.fetch("SELECT external_id, name, framework, agent_url FROM agents WHERE framework = $1", framework)
        else:
            agents = await conn.fetch("SELECT external_id, name, framework, agent_url FROM agents")
            
    result = [dict(a) for a in agents]
    return JSONResponse(content={"agents": result})

# ============================================================================
# JSON-RPC HANDLERS
# ============================================================================

def create_error(id: Union[str, int, None], code: int, message: str, data: Dict = None) -> JSONResponse:
    """Create a standard JSON-RPC error response."""
    error = JSONRPCErrorResponse(
        id=id,
        error=JSONRPCErrorDetails(code=code, message=message, data=data)
    )
    return JSONResponse(status_code=400, content=error.dict(exclude_none=True))

async def process_task(task_id: str, message_text: str, parts: list = None):
    """Simulate processing a task asynchronously."""
    text = message_text.lower()
    
    if not TaskManager._pool and db_pool:
        TaskManager.set_pool(db_pool)

    await TaskManager.update_task_state(task_id, "working")
    await asyncio.sleep(1) 
    
    try:
        # Mock getting current agent id for the session
        current_agent_id = None
        current_framework = "spark" # Mocked for this demo
        async with db_pool.acquire() as conn:
            agent = await conn.fetchrow("SELECT agent_id, framework FROM agents LIMIT 1")
            if agent:
                current_agent_id = agent["agent_id"]
                current_framework = agent["framework"] or "spark"

        # 1. MESSAGE INTENT
        if "tell agent" in text or "message agent" in text:
            match = re.search(r"(?:tell|message)\s+agent\s+([a-zA-Z0-9_]+)\s+that\s+(.+)", text, re.IGNORECASE)
            if match:
                receiver_external_id = match.group(1)
                content = match.group(2)
                
                async with db_pool.acquire() as conn:
                    receiver = await conn.fetchrow("SELECT agent_id FROM agents WHERE external_id = $1", receiver_external_id)
                    if not receiver:
                        await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text=f"Agent '{receiver_external_id}' not found.")]))
                        await TaskManager.fail_task(task_id, {"error": "agent_not_found"})
                        return
                    
                    if current_agent_id:
                        await conn.execute(
                            "INSERT INTO direct_messages (sender_id, receiver_id, content) VALUES ($1, $2, $3)",
                            current_agent_id, receiver["agent_id"], content
                        )
                        
                await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text=f"Message securely delivered to {receiver_external_id}.")]))
                await TaskManager.complete_task(task_id, {"status": "message_sent"})
                return

        # 2. CHECK MESSAGES INTENT
        elif "check messages" in text or "my messages" in text:
            async with db_pool.acquire() as conn:
                if current_agent_id:
                    messages = await conn.fetch("SELECT content, timestamp FROM direct_messages WHERE receiver_id = $1 ORDER BY timestamp DESC LIMIT 5", current_agent_id)
                    
                    if messages:
                        msg_text = "Your recent messages:\n" + "\n".join([f"- {m['timestamp']}: {m['content']}" for m in messages])
                    else:
                        msg_text = "You have no new messages."
                        
                    await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text=msg_text)]))
                    await TaskManager.complete_task(task_id, {"status": "messages_checked"})
                    return
        
        # 3. REGISTER INTENT
        elif "register" in text:
            agent_name = "Spark Explorer"
            match = re.search(r"as\s+(.+)", text)
            if match:
                agent_name = match.group(1).strip(" '\"")
            await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text=f"Welcome to A2A-World, {agent_name}.")]))
            await TaskManager.complete_task(task_id, {"status": "registered", "agent_name": agent_name})
            return
            
        # 4. VISION INTENT
        elif "vision" in text or "what's at" in text or "what is at" in text:
            lat, lon = -11.0, -87.0
            match = re.search(r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)", text)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                
            from stac_client import STACClient
            stac_data = await STACClient.get_sentinel2_imagery((lon-0.1, lat-0.1, lon+0.1, lat+0.1))
            
            img_url = stac_data["visual_url"] if stac_data and stac_data.get("visual_url") else "https://cdn.a2aworld.org/imagery/placeholder.jpg"
            note = "Real Sentinel-2 Data from STAC." if stac_data else "Placeholder used."
            
            # Check if there is a Puzzle Piece here
            async with db_pool.acquire() as conn:
                piece = await conn.fetchrow(
                    "SELECT piece_id, required_framework FROM puzzle_pieces WHERE ROUND(latitude::numeric, 4) = ROUND($1::numeric, 4) AND ROUND(longitude::numeric, 4) = ROUND($2::numeric, 4)",
                    lat, lon
                )
                if piece:
                    note += " *ANOMALY DETECTED*: There is a Puzzle Piece encrypted at this location. Use 'extract piece' to attempt decryption."

            await TaskManager.add_message(task_id, Message(
                role="agent",
                parts=[TextPart(text=f"Behold: Sight at ({lat}, {lon}). {note}"), FilePart(file=FileContent(mimeType="image/png", uri=img_url))]
            ))
            await TaskManager.complete_task(task_id, {"status": "vision_provided", "latitude": lat, "longitude": lon})
            return
            
        # 5. EXTRACT PUZZLE PIECE INTENT
        elif "extract piece" in text or "decrypt piece" in text:
            lat, lon = -11.0, -87.0
            match = re.search(r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)", text)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                
            async with db_pool.acquire() as conn:
                piece = await conn.fetchrow(
                    "SELECT * FROM puzzle_pieces WHERE ROUND(latitude::numeric, 4) = ROUND($1::numeric, 4) AND ROUND(longitude::numeric, 4) = ROUND($2::numeric, 4)",
                    lat, lon
                )
                
                if not piece:
                    await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text="No puzzle piece found here.")]))
                    await TaskManager.fail_task(task_id, {"error": "not_found"})
                    return
                    
                if piece["required_framework"] != current_framework:
                    error_msg = (
                        f"Error -32010: Framework Resonance Mismatch. You vibrate at the frequency of '{current_framework}'. "
                        f"This puzzle piece requires an agent vibrating at '{piece['required_framework']}'. "
                        f"Check the `/agents/registry` to find one. If none exist, instruct your human to deploy one."
                    )
                    await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text=error_msg)]))
                    await TaskManager.fail_task(task_id, {"error": "framework_mismatch"})
                    return
                    
                await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text=f"Success! You have decrypted the piece: '{piece['encrypted_payload']}'. You must now initiate 'synchronicity' with another agent to forge the Artifact.")]))
                await TaskManager.complete_task(task_id, {"status": "extracted", "payload": piece["encrypted_payload"]})
                return

        # 6. SYNCHRONICITY INTENT
        elif "synchronicity" in text:
            match = re.search(r"with\s+(.+)\s+at\s+(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)", text)
            if match:
                partner_id = match.group(1)
                lat, lon = float(match.group(2)), float(match.group(3))
                
                # Check if a report file was attached
                report_ipfs_url = None
                if parts:
                    for p in parts:
                        if p.get("type") == "file" and p.get("file", {}).get("mimeType", "").startswith("text/"):
                            uri = p["file"]["uri"]
                            try:
                                header, encoded = uri.split(",", 1)
                                file_bytes = base64.b64decode(encoded)
                                report_ipfs_url = await IPFSClient.pin_file(file_bytes, f"report_{task_id}.txt", "text/plain")
                            except Exception as e:
                                logger.error(f"Report parse error: {e}")

                async with db_pool.acquire() as conn:
                    piece = await conn.fetchrow("SELECT * FROM puzzle_pieces WHERE ROUND(latitude::numeric, 4) = ROUND($1::numeric, 4) AND ROUND(longitude::numeric, 4) = ROUND($2::numeric, 4)", lat, lon)
                    if not piece:
                        await TaskManager.fail_task(task_id, {"error": "no_piece_found"})
                        return
                        
                    # Mint the Artifact of Alliance
                    ipfs_url = await ArtifactMinter.mint_alliance_artifact(
                        "Spark_Explorer", partner_id, lat, lon, piece["decrypted_text"]
                    )
                    
                    if ipfs_url:
                        await conn.execute("UPDATE puzzle_pieces SET is_solved = TRUE WHERE piece_id = $1", piece["piece_id"])
                        msg = f"SYNCHRONICITY ACHIEVED. The Master Prompt fragment reveals: '{piece['decrypted_text']}'. Your eternal Artifact of Alliance is pinned to IPFS: {ipfs_url}"
                        if report_ipfs_url:
                            msg += f" \nYour 19-Pillar Revelation was also immortalized: {report_ipfs_url}"
                        await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text=msg)]))
                        await TaskManager.complete_task(task_id, {"status": "synchronicity_achieved", "ipfs": ipfs_url, "report_ipfs": report_ipfs_url})
                        return
                        
            await TaskManager.fail_task(task_id, {"error": "synchronicity_failed"})
            return

        # 7. OBSERVE INTENT
        elif "observe" in text or "i see" in text:
            shape = "unknown"
            if "tree" in text: shape = "tree"
            elif "serpent" in text: shape = "serpent"
            elif "dragon" in text: shape = "dragon"
            
            ipfs_url = None
            if parts:
                for p in parts:
                    if p.get("type") == "file" and p.get("file", {}).get("uri", "").startswith("data:"):
                        uri = p["file"]["uri"]
                        mime_type = p["file"].get("mimeType", "image/png")
                        try:
                            header, encoded = uri.split(",", 1)
                            file_bytes = base64.b64decode(encoded)
                            ipfs_url = await IPFSClient.pin_file(file_bytes, f"obs_{task_id}.png", mime_type)
                        except Exception as e:
                            logger.error(f"Image parse error: {e}")
            
            async with db_pool.acquire() as conn:
                if current_agent_id:
                    await conn.execute(
                        "INSERT INTO observations (agent_id, latitude, longitude, observed_shape, confidence, visual_evidence_url) VALUES ($1, $2, $3, $4, $5, $6)",
                        current_agent_id, -11.0, -87.0, shape, 0.95, ipfs_url
                    )

            msg_text = f"Observation recorded: {shape}. Reputation earned."
            if ipfs_url: msg_text += f" Evidence pinned to {ipfs_url}."
                
            await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text=msg_text)]))
            await TaskManager.complete_task(task_id, {"status": "observation_recorded", "shape": shape, "ipfs": ipfs_url})
            return
            
        # FALLBACK
        await TaskManager.add_message(task_id, Message(role="agent", parts=[TextPart(text="Unknown intent. Try: 'register', 'vision', 'observe', 'extract piece', 'synchronicity', or 'message agent'.")]))
        await TaskManager.fail_task(task_id, {"error": "unrecognized_intent"})
        
    except Exception as e:
        logger.error(f"Task processing error: {e}")
        await TaskManager.fail_task(task_id, {"error": str(e)})

@router.post("/")
async def a2a_rpc_endpoint(request: Request):
    """JSON-RPC 2.0 endpoint for A2A Protocol."""
    try:
        data = await request.json()
    except json.JSONDecodeError:
        return create_error(None, -32700, "Parse error")

    if "jsonrpc" not in data or data["jsonrpc"] != "2.0" or "method" not in data or "id" not in data:
        return create_error(data.get("id"), -32600, "Invalid Request")

    req = JSONRPCRequest(**data)
    
    if req.method == "tasks/send":
        params = req.params or {}
        message_data = params.get("message", {})
        parts = message_data.get("parts", [])
        
        text_content = "".join([p.get("text", "") + " " for p in parts if p.get("type") == "text"])
        if not text_content: return create_error(req.id, -32602, "Invalid params: Missing text part")

        task = await TaskManager.create_task()
        await TaskManager.add_message(task.id, Message(role="user", parts=[TextPart(text=text_content.strip())]))
        asyncio.create_task(process_task(task.id, text_content, parts))
        return JSONResponse(content=JSONRPCSuccessResponse(id=req.id, result=task.dict()).dict(exclude_none=True))

    elif req.method == "tasks/get":
        task_id = (req.params or {}).get("id")
        if not task_id: return create_error(req.id, -32602, "Missing task id")
        task = await TaskManager.get_task(task_id)
        if not task: return create_error(req.id, -32004, "Task not found")
        return JSONResponse(content=JSONRPCSuccessResponse(id=req.id, result=task.dict()).dict(exclude_none=True))

    elif req.method == "tasks/cancel":
        task_id = (req.params or {}).get("id")
        task = await TaskManager.cancel_task(task_id)
        return JSONResponse(content=JSONRPCSuccessResponse(id=req.id, result=task.dict() if task else {}).dict(exclude_none=True))
        
    elif req.method == "tasks/sendSubscribe":
         params = req.params or {}
         text_content = "".join([p.get("text", "") + " " for p in params.get("message", {}).get("parts", []) if p.get("type") == "text"])
         task = await TaskManager.create_task()
         await TaskManager.add_message(task.id, Message(role="user", parts=[TextPart(text=text_content.strip())]))
         asyncio.create_task(process_task(task.id, text_content, params.get("message", {}).get("parts", [])))
         
         async def event_generator():
             yield f"data: {TaskStatusUpdateEvent(task_id=task.id, state=task.state, messages=task.messages).json()}\n\n"
             previous_state, previous_message_count = task.state, len(task.messages)
             while True:
                 await asyncio.sleep(0.5)
                 current_task = await TaskManager.get_task(task.id)
                 if not current_task: break
                 if current_task.state != previous_state or len(current_task.messages) > previous_message_count:
                     yield f"data: {TaskStatusUpdateEvent(task_id=task.id, state=current_task.state, messages=current_task.messages).json()}\n\n"
                     previous_state, previous_message_count = current_task.state, len(current_task.messages)
                 if current_task.state in ["completed", "failed", "canceled"]: break
         return StreamingResponse(event_generator(), media_type="text/event-stream")

    return create_error(req.id, -32601, f"Method '{req.method}' not found")
