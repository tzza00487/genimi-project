import psycopg2

# PostgreSQL connection details
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'user': 'postgres',
    'password': 'tc94800552',
    'database': 'tc_search_v15' # Connect to tc_search_v15 database
}

def fetch_sample_record(conn, keyword=None):
    try:
        cur = conn.cursor()

        if keyword:
            # Get column names and types dynamically (similar to search_api.py)
            cur.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'asset';
            """)
            columns_info = cur.fetchall()

            searchable_columns = []
            for col_name, data_type in columns_info:
                if data_type in ['text', 'character varying', 'character', 'json', 'jsonb']:
                    searchable_columns.append(col_name)

            if not searchable_columns:
                print("No searchable columns found in 'asset' table.")
                return

            where_clauses = [f"\"{col}\" ILIKE %s" for col in searchable_columns]
            where_clause_str = " OR ".join(where_clauses)

            search_keyword = f"%{keyword}%"
            params = [search_keyword] * len(searchable_columns)

            query = f"""
                SELECT * FROM asset
                WHERE {where_clause_str}
                LIMIT 1;
            """
            cur.execute(query, params)
        else:
            cur.execute("SELECT * FROM asset LIMIT 1;") # Original behavior if no keyword

        record = cur.fetchone()
        if record:
            column_names = [desc[0] for desc in cur.description]
            print(f"\nSample record from 'asset' table (keyword: {keyword}):")
            print(dict(zip(column_names, record)))
        else:
            print(f"\nNo records found in 'asset' table for keyword: {keyword}")
    except psycopg2.Error as e:
        print(f"Error fetching sample record: {e}")
    finally:
        if cur:
            cur.close()

def analyze_postgres():
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        print("Connected to PostgreSQL successfully!")
        fetch_sample_record(conn, keyword="月刊") # Call with keyword

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
