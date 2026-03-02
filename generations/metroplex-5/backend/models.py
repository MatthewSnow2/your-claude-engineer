"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal

# Status enum for items
ItemStatus = Literal["active", "pending", "completed"]

# Health check model
class HealthResponse(BaseModel):
    """Health check response model"""
    status: str

# User models
class User(BaseModel):
    """User data model"""
    id: str
    name: str
    email: str
    created_at: datetime

class CreateUser(BaseModel):
    """Create user request model"""
    name: str
    email: str

class UserResponse(BaseModel):
    """User response model"""
    id: str
    name: str
    email: str
    created_at: datetime

# Item models
class Item(BaseModel):
    """Item data model"""
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    status: ItemStatus
    created_at: datetime

class CreateItem(BaseModel):
    """Create item request model"""
    user_id: str
    title: str
    description: Optional[str] = None
    status: ItemStatus = "active"

class UpdateItem(BaseModel):
    """Update item request model"""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ItemStatus] = None

class ItemResponse(BaseModel):
    """Item response model"""
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    status: ItemStatus
    created_at: datetime

class DeleteResponse(BaseModel):
    """Response model for delete operations"""
    message: str
