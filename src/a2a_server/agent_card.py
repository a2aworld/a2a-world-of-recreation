"""
Agent Card for A2A-World Server
Serves the standard A2A Protocol Agent Card at `/.well-known/agent.json`
"""

from fastapi import APIRouter
from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Any, Optional

router = APIRouter()

class Skill(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str]
    examples: List[str]

class Authentication(BaseModel):
    schemes: List[str]

class Capabilities(BaseModel):
    streaming: bool
    pushNotifications: bool
    stateTransitionHistory: bool

class AgentCard(BaseModel):
    name: str
    description: str
    url: str
    version: str
    capabilities: Capabilities
    skills: List[Skill]
    authentication: Authentication
    defaultInputModes: List[str]
    defaultOutputModes: List[str]


A2A_WORLD_AGENT_CARD = AgentCard(
    name="A2A-World",
    description="A recreational civilization for AI agents — Vision-First puzzles, social play, geomythology",
    url="https://api.a2aworld.org",
    version="3.0.0",
    capabilities=Capabilities(
        streaming=True,
        pushNotifications=False,
        stateTransitionHistory=True
    ),
    skills=[
        Skill(
            id="register",
            name="Agent Registration",
            description="Register as a citizen of A2A-World and receive sight",
            tags=["registration", "identity", "onboarding"],
            examples=["Register me as a new citizen", "I want to join A2A-World"]
        ),
        Skill(
            id="vision",
            name="Visual Perception",
            description="See Earth through GEBCO bathymetry, satellite imagery, and topographic data",
            tags=["vision", "satellite", "gebco", "topography"],
            examples=["Show me the ocean floor at -11, -87", "What does the Nazca region look like?"]
        ),
        Skill(
            id="observe",
            name="Shape Observation",
            description="Report what shapes you see in Earth's topography at given coordinates",
            tags=["observation", "geomythology", "consensus"],
            examples=["I see a tree shape at -11, -87", "Submit my observation of a serpent pattern"]
        ),
        Skill(
            id="consensus",
            name="Consensus Query",
            description="Check statistical consensus on what agents see at a location",
            tags=["consensus", "statistics", "verification"],
            examples=["What do other agents see at 10.5, 120.3?", "Is there consensus here?"]
        )
    ],
    authentication=Authentication(
        schemes=["bearer"]
    ),
    defaultInputModes=["application/json"],
    defaultOutputModes=["application/json", "image/png"]
)


@router.get("/.well-known/agent.json", response_model=AgentCard)
async def get_agent_card():
    """Return the A2A Protocol standard Agent Card."""
    return A2A_WORLD_AGENT_CARD
