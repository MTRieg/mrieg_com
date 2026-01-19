import os
from pathlib import Path

# Path to the SQLite database file used by stores. Can be overridden
# using the MRIEG_DB_PATH environment variable.
DB_PATH = os.environ.get("MRIEG_DB_PATH", str(Path(__file__).parent / "db.sqlite3"))
