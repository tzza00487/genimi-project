from fastapi import FastAPI, HTTPException
import mysql.connector
import psycopg2
from typing import List, Dict, Any

app = FastAPI()

# Database connection details (using container names for inter-container communication)
MARIADB_CONFIG = {
    'host': 'mariadb',
    'port': 3306,
    'user': 'root',
    'password': 'tc94800552',
    'database': 'tc_search_v15'
}

POSTGRES_CONFIG = {
    'host': 'postgresql',
    'port': 5432,
    'user': 'postgres',
    'password': 'tc94800552',
    'database': 'postgres' # Default db to connect to for creating the target DB
}

SEARCH_DB_CONFIG = {
    'host': 'postgresql',
    'port': 5432,
    'user': 'postgres',
    'password': 'tc94800552',
    'database': 'tc_search_v15' # Connect to the correct DB for searching
}


# PostgreSQL reserved keywords (partial list, expand as needed)
POSTGRES_RESERVED_KEYWORDS = {
    "user", "table", "column", "select", "insert", "update", "delete", "from", "where", "group", "order", "by", "limit", "offset", "and", "or", "not", "null", "true", "false"
}

def quote_identifier(name: str) -> str:
    """Quotes an identifier if it contains special characters or is a reserved keyword."""
    if '-' in name or '.' in name or name.lower() in POSTGRES_RESERVED_KEYWORDS:
        return f'"{name}"'
    return name

# --- NEW SEARCH ENDPOINT ---

@app.get("/search", response_model=List[Dict[str, Any]])
async def search_data(q: str | None = None):
    """
    Searches for a given query string in the 'asset' table.
    """
    if not q:
        return []

    conn = None
    try:
        # Use a dedicated connection for the search DB
        conn = psycopg2.connect(**SEARCH_DB_CONFIG)
        cursor = conn.cursor()

        # Search in the 'asset' table's 'name' column (ILIKE for case-insensitive search)
        # This is a simple approach. Full-text search would be more powerful but also more complex.
        query = "SELECT * FROM asset WHERE name ILIKE %s LIMIT 100;"
        
        cursor.execute(query, (f'%{q}%',))
        
        rows = cursor.fetchall()
        
        # Get column names from cursor.description
        columns = [desc[0] for desc in cursor.description]
        
        # Format results as a list of dictionaries
        results = [dict(zip(columns, row)) for row in rows]
        
        return results

    except psycopg2.Error as err:
        print(f"Database search error: {err}")
        raise HTTPException(status_code=500, detail=f"Database search error: {err}")
    finally:
        if conn:
            conn.close()


# --- Database Connection Functions ---
def get_mariadb_connection():
    try:
        conn = mysql.connector.connect(**MARIADB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"MariaDB connection error: {err}")

def get_postgres_connection():
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        return conn
    except psycopg2.Error as err:
        raise HTTPException(status_code=500, detail=f"PostgreSQL connection error: {err}")

# --- Data Type Mapping (Simplified for now, will expand as needed) ---
def map_mariadb_to_postgres_type(mariadb_type: str):
    mariadb_type = mariadb_type.lower()
    if "int" in mariadb_type:
        return "INTEGER"
    elif "varchar" in mariadb_type or "text" in mariadb_type:
        return "TEXT"
    elif "datetime" in mariadb_type or "timestamp" in mariadb_type:
        return "TIMESTAMP"
    elif "date" in mariadb_type:
        return "DATE"
    elif "decimal" in mariadb_type or "numeric" in mariadb_type:
        return "NUMERIC"
    elif "float" in mariadb_type or "double" in mariadb_type:
        return "DOUBLE PRECISION"
    elif "tinyint(1)" in mariadb_type: # MariaDB boolean
        return "BOOLEAN"
    # Add more mappings as needed
    return "TEXT" # Default to TEXT for unmapped types

# --- Migration Endpoints ---
@app.get("/")
async def read_root():
    return {"message": "FastAPI Migration App is running! Search at /search?q=your_query"}

@app.get("/migrate_schema")
async def migrate_schema():
    mariadb_conn = get_mariadb_connection()
    postgres_conn = get_postgres_connection()

    try:
        mariadb_cursor = mariadb_conn.cursor()
        postgres_cursor = postgres_conn.cursor()
        postgres_conn.autocommit = True # For CREATE DATABASE

        # 1. Create the target database in PostgreSQL if it doesn't exist
        target_db_name = MARIADB_CONFIG['database']
        try:
            postgres_cursor.execute(f"CREATE DATABASE {target_db_name}")
            print(f"Database {target_db_name} created in PostgreSQL.")
        except psycopg2.errors.DuplicateDatabase:
            print(f"Database {target_db_name} already exists in PostgreSQL.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error creating PostgreSQL database: {e}")
        
        

        # 2. Get table names from MariaDB
        mariadb_cursor.execute("SHOW TABLES")
        tables = [table[0] for table in mariadb_cursor.fetchall()]
        
        migration_summary = {}

        for table_name in tables:
            # Skip problematic table names
            if '@' in table_name or '.' in table_name:
                print(f"Skipping problematic table: {table_name}")
                migration_summary[table_name] = "Skipped (problematic name)"
                continue

            print(f"Migrating schema for table: {table_name}")
            try:
                # Get table schema from MariaDB
                mariadb_cursor.execute(f"DESCRIBE {table_name}")
                columns_info = mariadb_cursor.fetchall()

                create_table_sql = f"CREATE TABLE {quote_identifier(table_name)} (\n"
                column_definitions = []
                for col in columns_info:
                    col_name = quote_identifier(col[0]) # Quote column name
                    mariadb_type = col[1]
                    is_nullable = "NOT NULL" if col[2] == "NO" else "NULL"
                    
                    # Handle default values, especially current_timestamp()
                    default_val = ""
                    if col[4] is not None:
                        if "current_timestamp" in str(col[4]).lower():
                            default_val = "DEFAULT CURRENT_TIMESTAMP"
                        else:
                            default_val = f"DEFAULT '{col[4]}'"
                    
                    extra = col[5] # e.g., auto_increment

                    postgres_type = map_mariadb_to_postgres_type(mariadb_type)
                    
                    # Handle primary key and auto-increment (SERIAL for PostgreSQL)
                    pk_constraint = ""
                    if "pri" in col[3].lower():
                        pk_constraint = "PRIMARY KEY"
                        if "auto_increment" in extra.lower():
                            postgres_type = "SERIAL" # PostgreSQL auto-increment

                    column_definitions.append(f"    {col_name} {postgres_type} {is_nullable} {default_val} {pk_constraint}".strip())
                
                create_table_sql += ",\n".join(column_definitions)
                create_table_sql += "\n);"
                
                # Create table in PostgreSQL
                postgres_cursor.execute(create_table_sql)
                postgres_conn.commit()
                migration_summary[table_name] = "Schema migrated successfully"
                print(f"Schema for table {table_name} created in PostgreSQL.")

            except Exception as e:
                postgres_conn.rollback()
                migration_summary[table_name] = f"Schema migration failed: {e}"
                print(f"Schema migration for table {table_name} failed: {e}")

        return {"status": "Schema migration initiated", "summary": migration_summary}

    finally:
        if mariadb_conn:
            mariadb_conn.close()
        if postgres_conn:
            postgres_conn.close()

@app.get("/migrate_data/{table_name}")
async def migrate_data(table_name: str, chunk_size: int = 10000):
    mariadb_conn = get_mariadb_connection()
    postgres_conn = get_postgres_connection()

    try:
        mariadb_cursor = mariadb_conn.cursor(dictionary=True) # Fetch as dictionaries
        postgres_cursor = postgres_conn.cursor()

        

        # Get columns from MariaDB to ensure correct order for insertion
        mariadb_cursor.execute(f"SELECT * FROM {table_name} LIMIT 0")
        mariadb_cursor.fetchall() # Consume the empty result set
        mariadb_columns = [col[0] for col in mariadb_cursor.description]

        # Prepare insert statement for PostgreSQL
        columns_str = ", ".join([quote_identifier(col) for col in mariadb_columns])
        placeholders = ", ".join(["%s"] * len(mariadb_columns))
        insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

        offset = 0
        rows_migrated = 0
        while True:
            mariadb_cursor.execute(f"SELECT * FROM {table_name} LIMIT {chunk_size} OFFSET {offset}")
            rows = mariadb_cursor.fetchall()
            if not rows:
                break

            # Prepare data for PostgreSQL insertion
            data_to_insert = []
            for row in rows:
                # Convert dictionary values to a list in the correct order
                data_to_insert.append(tuple(row[col] for col in mariadb_columns))
            
            try:
                postgres_cursor.executemany(insert_sql, data_to_insert)
                postgres_conn.commit()
                rows_migrated += len(rows)
                print(f"Migrated {len(rows)} rows to {table_name}. Total: {rows_migrated}")
            except Exception as e:
                postgres_conn.rollback()
                print(f"Error migrating data for table {table_name} at offset {offset}: {e}")
                raise HTTPException(status_code=500, detail=f"Data migration failed for {table_name}: {e}")

            offset += chunk_size
        
        return {"status": "Data migration complete", "table": table_name, "rows_migrated": rows_migrated}

    finally:
        if mariadb_conn:
            mariadb_conn.close()
        if postgres_conn:
            postgres_conn.close()

@app.get("/migrate_all_data")
async def migrate_all_data(chunk_size: int = 10000):
    mariadb_conn = get_mariadb_connection()
    mariadb_cursor = mariadb_conn.cursor()
    
    try:
        mariadb_cursor.execute("SHOW TABLES")
        tables = [table[0] for table in mariadb_cursor.fetchall()]
        
        full_migration_summary = {}
        for table_name in tables:
            # Skip problematic table names for data migration
            if '@' in table_name or '.' in table_name:
                print(f"Skipping problematic table for data migration: {table_name}")
                full_migration_summary[table_name] = {"status": "skipped", "detail": "Problematic name"}
                continue

            print(f"Starting data migration for table: {table_name}")
            try:
                result = await migrate_data(table_name, chunk_size)
                full_migration_summary[table_name] = result
            except HTTPException as e:
                full_migration_summary[table_name] = {"status": "failed", "detail": e.detail}
            except Exception as e:
                full_migration_summary[table_name] = {"status": "failed", "detail": str(e)}
        
        return {"status": "Full data migration initiated", "summary": full_migration_summary}
    finally:
        if mariadb_conn:
            mariadb_conn.close()

@app.get("/verify_counts")
async def verify_counts():
    mariadb_conn = None
    postgres_conn = None
    verification_results = {}

    try:
        # Connect to MariaDB
        mariadb_conn = get_mariadb_connection()
        mariadb_cursor = mariadb_conn.cursor()

        # Connect to PostgreSQL target database
        pg_config_with_db = POSTGRES_CONFIG.copy()
        pg_config_with_db['database'] = MARIADB_CONFIG['database']
        try:
            postgres_conn = psycopg2.connect(**pg_config_with_db)
            postgres_cursor = postgres_conn.cursor()
        except psycopg2.Error as err:
            raise HTTPException(status_code=500, detail=f"PostgreSQL connection to DB {pg_config_with_db['database']} error: {err}")

        # Get all tables from MariaDB
        mariadb_cursor.execute("SHOW TABLES")
        tables = [table[0] for table in mariadb_cursor.fetchall()]

        for table_name in tables:
            if '@' in table_name or '.' in table_name:
                verification_results[table_name] = {
                    "status": "skipped",
                    "mariadb_count": -1,
                    "postgres_count": -1
                }
                continue

            try:
                # Get count from MariaDB
                mariadb_cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                mariadb_count = mariadb_cursor.fetchone()[0]

                # Get count from PostgreSQL
                # Use quote_identifier to handle reserved keywords
                quoted_table_name = quote_identifier(table_name)
                postgres_cursor.execute(f"SELECT COUNT(*) FROM {quoted_table_name}")
                postgres_count = postgres_cursor.fetchone()[0]
                
                # Compare counts
                match = mariadb_count == postgres_count
                verification_results[table_name] = {
                    "mariadb_count": mariadb_count,
                    "postgres_count": postgres_count,
                    "match": match,
                    "status": "verified"
                }
                print(f"Verifying {table_name}: MariaDB({mariadb_count}) vs PostgreSQL({postgres_count}) -> {'Match' if match else 'Mismatch'}")

            except Exception as e:
                print(f"Error verifying table {table_name}: {e}")
                verification_results[table_name] = {
                    "status": "error",
                    "detail": str(e)
                }

        return {"status": "Verification complete", "results": verification_results}

    finally:
        if mariadb_conn:
            mariadb_conn.close()
        if postgres_conn:
            postgres_conn.close()
