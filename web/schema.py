"""
Lab 8 — Pydantic schemas for the FastAPI REST endpoints.

Defines the request and response contracts for the /chat and /stream
endpoints, ensuring strict validation of client payloads.
"""

from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Chat endpoint schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    """Request body for POST /chat and POST /stream."""
    message: str = Field(
        ...,
        description="The user's message to the onboarding agent.",
        min_length=1,
        max_length=2000,
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Optional thread ID for persistent conversations. "
                    "If omitted, a new thread is created.",
    )
    mode: str = Field(
        default="single",
        description="Agent mode: 'single' for ReAct agent, 'multi' for multi-agent.",
        pattern="^(single|multi)$",
    )


class ToolCallInfo(BaseModel):
    """Details of a tool invocation within the agent's response."""
    name: str = Field(description="Name of the tool that was called.")
    args: dict = Field(description="Arguments passed to the tool.")


class ChatResponse(BaseModel):
    """Response body from POST /chat."""
    response: str = Field(description="The agent's final response text.")
    tool_calls: list[ToolCallInfo] = Field(
        default_factory=list,
        description="List of tool calls made during processing.",
    )
    mode: str = Field(description="Agent mode used: 'single' or 'multi'.")
    thread_id: Optional[str] = Field(
        default=None,
        description="Thread ID for session continuity.",
    )
    status: str = Field(
        default="success",
        description="Response status: 'success' or 'error'.",
    )


class ErrorResponse(BaseModel):
    """Error response body."""
    error: str = Field(description="Error message.")
    detail: Optional[str] = Field(default=None, description="Additional detail.")
