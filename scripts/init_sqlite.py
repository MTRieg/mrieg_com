#!/usr/bin/env python3
"""Initialize SQLite database from schema.sql using Python's sqlite3 module."""
import sqlite3
import sys
import os
from pathlib import Path

def init_db(db_path: str, schema_path: str) -> None:
    """Initialize SQLite database from schema file."""
    db_path = Path(db_path).resolve()
    schema_path = Path(schema_path).resolve()
    
    if not schema_path.exists():
        print(f"[INIT] ✗ Error: Schema file not found at {schema_path}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Connect and initialize database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Drop all existing tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [t[0] for t in cursor.fetchall()]
        for table in existing_tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
        
        # Load and execute schema
        sql = schema_path.read_text()
        conn.executescript(sql)
        conn.commit()
        
        # Verify critical tables exist
        critical_tables = ['games', 'game_settings', 'game_state', 'players']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        created_tables = {t[0] for t in cursor.fetchall()}
        
        for table in critical_tables:
            if table not in created_tables:
                print(f"[INIT] ✗ Error: Missing critical table '{table}'", file=sys.stderr)
                conn.close()
                sys.exit(1)
        
        conn.close()
        # Ensure database file is readable and writable by all users (especially for Docker containers)
        os.chmod(str(db_path), 0o666)
        print(f"[INIT] ✓ Database initialized successfully")
        
    except sqlite3.Error as e:
        print(f"[INIT] ✗ Error: Failed to initialize database: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "./dev.db"
    schema_path = sys.argv[2] if len(sys.argv) > 2 else "./db/schema.sql"
    init_db(db_path, schema_path)

