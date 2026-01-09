from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from contextlib import contextmanager

from auth import hash_password, verify_password, create_access_token, get_current_user
from query_config import get_query, set_query, get_all_queries, get_query_with_sql, delete_query, validate_query_syntax, get_default_query
from logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])
SQLITE_DB_PATH = "building_schedules.db"

@contextmanager
def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    is_admin: bool

class QueryRequest(BaseModel):
    query_name: str
    query_sql: str
    description: Optional[str] = ""

class QueryResponse(BaseModel):
    query_name: str
    query_sql: str
    description: str
    created_at: Optional[str]
    updated_at: Optional[str]

# Auth Dependencies
def get_current_admin_user(authorization: Optional[str] = Header(None)) -> tuple:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    username = get_current_user(token)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    with get_sqlite_connection() as conn:
        cursor = conn.execute("SELECT is_admin FROM admin_users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
        return username, bool(row['is_admin'])

def require_admin(auth_info: tuple = Depends(get_current_admin_user)) -> str:
    username, is_admin = auth_info
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return username

# Routes
@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    with get_sqlite_connection() as conn:
        cursor = conn.execute("SELECT username, password_hash, is_admin FROM admin_users WHERE username = ?", (request.username,))
        row = cursor.fetchone()
        if not row or not verify_password(request.password, row['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token = create_access_token(data={"sub": request.username})
        return LoginResponse(access_token=access_token, token_type="bearer", username=request.username, is_admin=bool(row['is_admin']))

@router.get("/queries")
async def list_queries(auth_info: tuple = Depends(get_current_admin_user)):
    username, is_admin = auth_info
    queries = [
        {'query_name': 'device_query', 'description': 'Main configuration for Device_TBL retrieval'},
        {'query_name': 'building_query', 'description': 'Main configuration for Building_TBL retrieval'}
    ]
    return {"queries": queries, "is_admin": is_admin}

@router.get("/queries/{query_name}", response_model=QueryResponse)
async def get_query_details(query_name: str, auth_info: tuple = Depends(get_current_admin_user)):
    query_data = get_query_with_sql(query_name)
    if not query_data:
        raise HTTPException(status_code=404, detail=f"Query '{query_name}' not found")
    return QueryResponse(**query_data)

@router.post("/queries")
async def update_query(request: QueryRequest, admin_username: str = Depends(require_admin)):
    is_valid, error_message = validate_query_syntax(request.query_sql)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid query: {error_message}")
    if not set_query(request.query_name, request.query_sql, request.description):
        raise HTTPException(status_code=500, detail="Failed to save query")
    return {"success": True, "message": f"Query '{request.query_name}' saved successfully"}