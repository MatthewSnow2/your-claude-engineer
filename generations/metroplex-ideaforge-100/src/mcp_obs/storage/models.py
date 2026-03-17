"""Pydantic data models for MCP observability layer."""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ToolCallStatus(str, Enum):
    """Status of a tool call execution."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    RETRY = "retry"


class ToolCall(BaseModel):
    """Record of a single tool call execution."""
    id: str = Field(..., description="Unique tool call identifier")
    session_id: str = Field(..., description="Parent session ID")
    tool_name: str = Field(..., description="Name of the called tool")
    parameters: Dict[str, Any] = Field(..., description="Tool call parameters")
    response: Optional[Dict[str, Any]] = Field(None, description="Tool response data")
    status: ToolCallStatus = Field(..., description="Execution status")
    execution_time_ms: int = Field(..., description="Execution duration in milliseconds")
    tokens_consumed: int = Field(0, description="Tokens used for this call")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    error_message: Optional[str] = Field(None, description="Error details if failed")
    retry_count: int = Field(0, description="Number of retry attempts")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class AgentSession(BaseModel):
    """Record of an agent execution session."""
    session_id: str = Field(..., description="Unique session identifier")
    agent_version: Optional[str] = Field(None, description="Agent version identifier")
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = Field(None, description="Session completion time")
    total_tokens: int = Field(0, description="Total tokens consumed")
    total_cost_usd: float = Field(0.0, description="Session cost in USD")
    tool_calls_count: int = Field(0, description="Number of tool calls made")
    success_rate: float = Field(0.0, description="Percentage of successful tool calls")
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Session context")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class ToolEffectivenessMetric(BaseModel):
    """Tool effectiveness analysis metrics."""
    tool_name: str = Field(..., description="Tool identifier")
    measurement_window_hours: int = Field(..., description="Analysis time window")
    total_calls: int = Field(..., description="Total calls in window")
    success_count: int = Field(..., description="Successful calls")
    failure_count: int = Field(..., description="Failed calls")
    timeout_count: int = Field(..., description="Timed out calls")
    retry_count: int = Field(..., description="Retry attempts")
    average_execution_ms: float = Field(..., description="Average execution time")
    effectiveness_score: float = Field(..., description="Calculated effectiveness score 0-100")
    failure_patterns: List[str] = Field(default_factory=list, description="Common failure types")
    improvement_suggestions: List[str] = Field(default_factory=list, description="Optimization recommendations")
    trend: str = Field(default="stable", description="Trend: improving, stable, or degrading")
    last_calculated: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class FailurePattern(BaseModel):
    """Detected failure pattern in agent execution."""
    pattern_id: str = Field(..., description="Unique pattern identifier")
    pattern_type: str = Field(..., description="Category of failure")
    occurrence_count: int = Field(..., description="Times this pattern occurred")
    affected_tools: List[str] = Field(..., description="Tools affected by this pattern")
    sample_error_message: str = Field(..., description="Representative error message")
    suggested_fixes: List[str] = Field(..., description="Recommended solutions")
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    severity: str = Field(..., description="Impact level: low/medium/high/critical")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class CostAnalysis(BaseModel):
    """Cost analysis for a time period."""
    time_period: str = Field(..., description="Analysis period (daily/weekly/monthly)")
    period_start: datetime = Field(..., description="Period start time")
    period_end: datetime = Field(..., description="Period end time")
    total_cost_usd: float = Field(..., description="Total cost for period")
    total_tokens: int = Field(..., description="Total tokens consumed")
    session_count: int = Field(..., description="Number of sessions")
    cost_per_session: float = Field(..., description="Average cost per session")
    most_expensive_tools: List[str] = Field(..., description="Tools with highest cost impact")
    optimization_opportunities: List[str] = Field(..., description="Cost reduction suggestions")
    projected_monthly_cost: float = Field(..., description="Projected monthly spend")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class ReplayStep(BaseModel):
    """Step in a session replay."""
    step_number: int = Field(..., description="Step index in replay timeline")
    tool_call: ToolCall = Field(..., description="Tool call for this step")
    elapsed_time_ms: int = Field(..., description="Time since session start in milliseconds")
    cumulative_tokens: int = Field(..., description="Total tokens consumed up to this step")
    cumulative_cost: float = Field(..., description="Total cost incurred up to this step")
    context_summary: str = Field(..., description="Summary of what's happening at this step")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }
