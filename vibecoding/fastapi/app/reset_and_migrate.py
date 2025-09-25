# reset_and_migrate.py
import mysql.connector
import psycopg2
import sys

# --- CONFIGS and HELPERS (Copied from main.py) ---

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
    'database': 'tc_search_v15' # Connect directly to the target DB
}

POSTGRES_RESERVED_KEYWORDS = {
    "user", "table", "column", "select", "insert", "update", "delete", "from", "where", "group", "order", "by", "limit", "offset", "and", "or", "not", "null", "true", "false"
}

def quote_identifier(name: str) -> str:
    if '-' in name or '.' in name or name.lower() in POSTGRES_RESERVED_KEYWORDS:
        return f'"{name}"'
    return name

# --- MAIN SCRIPT LOGIC ---

def truncate_postgres_tables():
    """Connects to PostgreSQL and truncates all tables."""
    pg_conn = None
    print("--- Step 1: Truncating all tables in PostgreSQL ---")
    try:
        pg_conn = psycopg2.connect(**POSTGRES_CONFIG)
        pg_cursor = pg_conn.cursor()

        # Get all tables in the public schema
        pg_cursor.execute("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
        """)
        tables = [row[0] for row in pg_cursor.fetchall()]

        for table_name in tables:
            try:
                print(f"Truncating table: {table_name}...")
                # Use CASCADE to handle foreign keys and RESTART IDENTITY to reset sequences
                pg_cursor.execute(f"TRUNCATE TABLE {quote_identifier(table_name)} RESTART IDENTITY CASCADE")
                print(f"Table {table_name} truncated successfully.")
            except Exception as e:
                print(f"Could not truncate table {table_name}. Reason: {e}", file=sys.stderr)
                pg_conn.rollback() # Rollback this specific operation
        
        pg_conn.commit()
        print("--- Step 1: Truncation complete. ---")
        print() # Add a blank line for readability

    except psycopg2.Error as err:
        print(f"PostgreSQL connection error during truncation: {err}", file=sys.stderr)
        sys.exit(1)
    finally:
        if pg_conn:
            pg_conn.close()

def migrate_all_data():
    """Migrates all data from MariaDB to PostgreSQL."""
    print("--- Step 2: Starting full data migration ---")
    mariadb_conn = None
    postgres_conn = None
    
    try:
        mariadb_conn = mysql.connector.connect(**MARIADB_CONFIG)
        postgres_conn = psycopg2.connect(**POSTGRES_CONFIG)
        
        mariadb_cursor = mariadb_conn.cursor()
        
        mariadb_cursor.execute("SHOW TABLES")
        tables = [table[0] for table in mariadb_cursor.fetchall()]
        
        for table_name in tables:
            if '@' in table_name or '.' in table_name:
                print(f"Skipping problematic table for data migration: {table_name}")
                continue

            print(f"--- Starting data migration for table: {table_name} ---")
            migrate_table_data(table_name, mariadb_conn, postgres_conn)
        
        print("\n--- Step 2: Full data migration process finished. ---")

    except Exception as e:
        print(f"An error occurred during the migration process: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if mariadb_conn:
            mariadb_conn.close()
        if postgres_conn:
            postgres_conn.close()

def migrate_table_data(table_name: str, mariadb_conn, postgres_conn, chunk_size: int = 10000):
    """Migrates data for a single table."""
    mariadb_cursor = mariadb_conn.cursor(dictionary=True)
    postgres_cursor = postgres_conn.cursor()

    try:
        # Get columns from MariaDB to ensure correct order
        mariadb_cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 0")
        mariadb_cursor.fetchall()
        mariadb_columns = [col[0] for col in mariadb_cursor.description]

        # Prepare insert statement for PostgreSQL
        columns_str = ", ".join([quote_identifier(col) for col in mariadb_columns])
        placeholders = ", ".join(["%s"] * len(mariadb_columns))
        insert_sql = f"INSERT INTO {quote_identifier(table_name)} ({columns_str}) VALUES ({placeholders})"

        offset = 0
        total_rows_migrated = 0
        while True:
            mariadb_cursor.execute(f"SELECT * FROM `{table_name}` LIMIT {chunk_size} OFFSET {offset}")
            rows = mariadb_cursor.fetchall()
            if not rows:
                break

            data_to_insert = [tuple(row[col] for col in mariadb_columns) for row in rows]
            
            try:
                postgres_cursor.executemany(insert_sql, data_to_insert)
                postgres_conn.commit()
                total_rows_migrated += len(rows)
                print(f"Migrated {len(rows)} rows to {table_name}. Total: {total_rows_migrated}")
            except Exception as e:
                postgres_conn.rollback()
                print(f"Error migrating data chunk for table {table_name} at offset {offset}: {e}", file=sys.stderr)
                # Decide whether to stop or continue
                # For now, we stop on first error to ensure data integrity
                raise e

            offset += chunk_size
        
        print(f"--- Finished data migration for table: {table_name}. Total rows: {total_rows_migrated} ---")

    except Exception as e:
        print(f"Failed to migrate data for table {table_name}. Reason: {e}", file=sys.stderr)
        # Re-raise the exception to be caught by the main loop
        raise e
    finally:
        mariadb_cursor.close()
        postgres_cursor.close()


if __name__ == "__main__":
    truncate_postgres_tables()
    migrate_all_data()