#!/usr/bin/env python3
"""
Script to fix Alembic version table when a revision is missing.
This directly updates the alembic_version table in the database.
"""
import os
import sys

# Add application to path
sys.path.insert(0, '/application')

from app.connections.database import execute_raw_sql, get_db_session
from sqlalchemy import text

# Target revision (head)
target_revision = "d3c38e1d1b57"

try:
    # Check current version
    result = execute_raw_sql("SELECT version_num FROM alembic_version", fetch_results=True)
    
    if result:
        current_version = result[0]['version_num']
        print(f"Current version in database: {current_version}")
    else:
        print("No version found in database, inserting new version")
        with get_db_session(read_only=False) as db:
            db.execute(text(f"INSERT INTO alembic_version (version_num) VALUES ('{target_revision}')"))
        print(f"Successfully inserted alembic_version: {target_revision}")
        sys.exit(0)
    
    # Update to target revision
    with get_db_session(read_only=False) as db:
        db.execute(text(f"UPDATE alembic_version SET version_num = '{target_revision}'"))
    
    # Verify update
    result = execute_raw_sql("SELECT version_num FROM alembic_version", fetch_results=True)
    new_version = result[0]['version_num']
    print(f"Updated version in database: {new_version}")
    print(f"Successfully updated alembic_version to {target_revision}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

