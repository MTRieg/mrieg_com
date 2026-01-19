from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import aiosqlite
import config

router = APIRouter()


@router.get("/knockout/infodump")
async def info_dump():
    """Dynamically query all tables from sqlite_master, returning rows as dicts with field names"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = await cursor.fetchall()
        
        result = {}
        for (table_name,) in tables:
            cursor = await db.execute(f"SELECT * FROM {table_name}")
            rows = await cursor.fetchall()
            # Convert Row objects to dicts for JSON serialization
            result[table_name] = [dict(row) for row in rows]
        return result


