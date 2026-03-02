"""
API routes for the AI Agent Analytics Platform
This module will contain all API endpoints
"""
import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status
from database import get_db
from models import UserResponse, ItemResponse, CreateItem, UpdateItem, DeleteResponse

router = APIRouter()

# Whitelist of allowed update fields for items
ALLOWED_UPDATE_FIELDS = {"title", "description", "status"}

# ========================================
# USER ENDPOINTS
# ========================================

@router.get("/users", response_model=List[UserResponse])
async def get_users():
    """Get all users"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email, created_at FROM users LIMIT 100")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch users")

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str):
    """Get user by ID"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, email, created_at FROM users WHERE id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch user")

# ========================================
# ITEM ENDPOINTS
# ========================================

@router.get("/items", response_model=List[ItemResponse])
async def get_items():
    """Get all items"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, user_id, title, description, status, created_at FROM items LIMIT 100")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch items")

@router.post("/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(item: CreateItem):
    """Create a new item"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Validate user_id exists
            cursor.execute("SELECT id FROM users WHERE id = ?", (item.user_id,))
            user = cursor.fetchone()
            if not user:
                raise HTTPException(status_code=400, detail="Referenced user does not exist")

            # Generate UUID for new item
            item_id = str(uuid.uuid4())

            # Insert new item
            cursor.execute(
                "INSERT INTO items (id, user_id, title, description, status) VALUES (?, ?, ?, ?, ?)",
                (item_id, item.user_id, item.title, item.description, item.status)
            )

            # Fetch and return the created item
            cursor.execute(
                "SELECT id, user_id, title, description, status, created_at FROM items WHERE id = ?",
                (item_id,)
            )
            row = cursor.fetchone()
            return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create item")

@router.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: str):
    """Get item by ID"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, user_id, title, description, status, created_at FROM items WHERE id = ?",
                (item_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Item not found")
            return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch item")

@router.put("/items/{item_id}", response_model=ItemResponse, status_code=200)
async def update_item(item_id: str, item: UpdateItem):
    """Update an existing item"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            # Check if item exists
            cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
            existing = cursor.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Item not found")

            # Build update from provided fields only (whitelist approach)
            update_data = item.model_dump(exclude_unset=True)
            if not update_data:
                # No fields to update, return existing item
                return dict(existing)

            # Validate only allowed fields
            for key in update_data:
                if key not in ALLOWED_UPDATE_FIELDS:
                    raise HTTPException(status_code=400, detail=f"Cannot update field: {key}")

            # Build parameterized query with whitelisted field names
            set_clauses = [f"{field} = ?" for field in update_data.keys()]
            values = list(update_data.values())
            values.append(item_id)

            cursor.execute(
                f"UPDATE items SET {', '.join(set_clauses)} WHERE id = ?",
                values
            )

            # Fetch and return updated item
            cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
            updated = cursor.fetchone()
            return dict(updated)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update item")

@router.delete("/items/{item_id}", response_model=DeleteResponse)
async def delete_item(item_id: str):
    """Delete an item"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()

            # Check if item exists
            cursor.execute("SELECT id FROM items WHERE id = ?", (item_id,))
            existing_item = cursor.fetchone()
            if not existing_item:
                raise HTTPException(status_code=404, detail="Item not found")

            # Delete the item
            cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))

            return {"message": "Item deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete item")
