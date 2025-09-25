import psycopg2

# PostgreSQL connection details
DB_CONFIG = {
    'host': '127.0.0.1',  # PostgreSQL container is mapped to localhost
    'port': 5432,
    'user': 'postgres',
    'password': 'tc94800552',
    'database': 'postgres' # Connect to default 'postgres' database initially
}

def analyze_postgres():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        print("Connected to PostgreSQL successfully!")

        # List databases
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
        databases = [db[0] for db in cur.fetchall()]
        print("\nDatabases in PostgreSQL:")
        for db in databases:
            print(f"- {db}")

        # For each database, list tables
        for db in databases:
            if db not in ['template0', 'template1']: # Skip template databases
                print(f"\n--- Tables in database: {db} ---")
                # Need to reconnect to switch databases
                db_config_with_db = DB_CONFIG.copy()
                db_config_with_db['database'] = db
                db_conn_specific = None
                try:
                    db_conn_specific = psycopg2.connect(**db_config_with_db)
                    db_cur_specific = db_conn_specific.cursor()
                    db_cur_specific.execute("""
                        SELECT tablename FROM pg_tables
                        WHERE schemaname = 'public';
                    """)
                    tables = [table[0] for table in db_cur_specific.fetchall()]
                    if tables:
                        for table in tables:
                            print(f"  - Table: {table}")
                            # Optionally, fetch row count and sample data (similar to MariaDB analysis)
                            # For now, just listing tables to confirm connectivity and basic structure
                    else:
                        print(f"  No tables found in public schema of database: {db}")
                except psycopg2.Error as db_err:
                    print(f"  Error connecting to database {db}: {db_err}")
                finally:
                    if db_conn_specific:
                        db_cur_specific.close()
                        db_conn_specific.close()

    except psycopg2.Error as err:
        print(f"Error: {err}")
    finally:
        if conn:
            cur.close()
            conn.close()
            print("\nPostgreSQL connection closed.")

if __name__ == "__main__":
    analyze_postgres()
