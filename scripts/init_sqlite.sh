#!/bin/bash
# Initialize SQLite database from schema.sql
# This script is idempotent and safe to run multiple times

DB_PATH="${1:-./dev.db}"
SCHEMA_PATH="${2:-./db/schema.sql}"

if [ ! -f "$SCHEMA_PATH" ]; then
    echo "Error: Schema file not found at $SCHEMA_PATH"
    exit 1
fi

echo "Initializing SQLite database at $DB_PATH from $SCHEMA_PATH..."

# Use sqlite3 to initialize the database
# The schema.sql uses CREATE TABLE IF NOT EXISTS, so this is idempotent
sqlite3 "$DB_PATH" < "$SCHEMA_PATH"

if [ $? -eq 0 ]; then
    echo "Database initialized successfully"
else
    echo "Error: Failed to initialize database"
    exit 1
fi
