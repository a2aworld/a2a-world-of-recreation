"""
A2A Protocol Models for A2A-World Server
Defines the Pydantic models for JSON-RPC 2.0 based A2A Protocol communication.
"""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


# ============================================================================
# Basic Types & Parts
# ============================================================================

class FileContent(BaseModel):
    mimeType: str = Field(..., description="MIME type of the file")
    uri: str = Field(..., description="URI of the file content")


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field(..., description="Text content")


class FilePart(BaseModel):
    type: Literal["file"] = "file"
    file: FileContent


class DataPart(BaseModel):
    type: Literal["data"] = "data"
    data: Dict[str, Any]


Part = Union[TextPart, FilePart, DataPart]


class Message(BaseModel):
    """A message within a task."""
    role: Literal["user", "agent", "system"] = Field(..., description="Role of the message sender")
    parts: List[Part] = Field(..., description="Content parts of the message")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Task Types
# ============================================================================

TaskState = Literal["submitted", "working", "input-required", "completed", "failed", "canceled"]


class Task(BaseModel):
    """An A2A Protocol task."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    state: TaskState = Field(default="submitted")
    messages: List[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class TaskStatusUpdateEvent(BaseModel):
    """Event payload for SSE streaming of task status."""
    task_id: str
    state: TaskState
    messages: List[Message] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# JSON-RPC 2.0 Envelopes
# ============================================================================

class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None


class JSONRPCErrorDetails(BaseModel):
    code: int
    message: str
    data: Optional[Dict[str, Any]] = None


class JSONRPCErrorResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int, None]
    error: JSONRPCErrorDetails


class JSONRPCSuccessResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int]
    result: Any

JSONRPCResponse = Union[JSONRPCSuccessResponse, JSONRPCErrorResponse]
