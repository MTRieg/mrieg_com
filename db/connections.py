from pathlib import Path
from typing import Dict, Optional
import aiosqlite


async def connect(db_path: str, pragmas: Optional[Dict[str, str]] = None) -> aiosqlite.Connection:
    """Open an aiosqlite connection and apply sensible pragmas.

    - Sets `row_factory` to `aiosqlite.Row` for named access.
    - Enables foreign keys by default.
    - Applies any additional PRAGMA settings supplied in `pragmas`.

    Returns an open connection; caller is responsible for closing it.
    """
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row

    # Ensure foreign keys are enabled and apply additional pragmas
    await conn.execute("PRAGMA foreign_keys = ON")
    if pragmas:
        for k, v in pragmas.items():
            await conn.execute(f"PRAGMA {k} = {v}")

    await conn.commit()
    return conn


async def init_db(db_path: str, schema_path: Optional[str] = None) -> None:
    """Initialize a SQLite database file using the provided SQL schema.

    If `schema_path` is not provided this function will look for `schema.sql`
    next to this module (i.e. `db/schema.sql`).
    """
    schema_file = (
        Path(schema_path) if schema_path else Path(__file__).parent / "schema.sql"
    )

    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    sql = schema_file.read_text()

    conn = await connect(db_path)
    try:
        # Remove SQL comments and split by semicolon to handle triggers/complex statements
        statements = []
        current = []
        for line in sql.split('\n'):
            # Strip SQL comments
            if '--' in line:
                line = line[:line.index('--')]
            line = line.strip()
            if line:
                current.append(line)
                if line.endswith(';'):
                    # Join and remove trailing semicolon before executing
                    stmt = ' '.join(current).rstrip(';').strip()
                    if stmt:
                        statements.append(stmt)
                    current = []
        
        # Execute each statement individually
        for statement in statements:
            if statement.strip():
                await conn.execute(statement)
        
        await conn.commit()
    finally:
        await conn.close()


async def ensure_db(db_path: str, schema_path: Optional[str] = None) -> None:
    """Create the database file if it doesn't exist, initializing schema.

    If the database already exists this is a no-op.
    """
    db_file = Path(db_path)
    if db_file.exists():
        return
    # Ensure parent directory exists
    if db_file.parent and not db_file.parent.exists():
        db_file.parent.mkdir(parents=True, exist_ok=True)

    await init_db(db_path, schema_path)
