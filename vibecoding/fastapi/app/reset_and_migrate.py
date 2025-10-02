# reset_and_migrate.py
import mysql.connector
import psycopg2
import sys

# --- CONFIGS and HELPERS (Copied from main.py) ---

MARIADB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'tc94800552',
    'database': 'tc_search_v15'
}

POSTGRES_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'user': 'user',
    'password': 'password',
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
    
    # --- Step 0: Ensure target database exists ---
    pg_maintenance_conn = None
    try:
        print("--- Step 0: Ensuring target database exists ---")
        maintenance_config = POSTGRES_CONFIG.copy()
        target_db_name = maintenance_config.pop('database') # Pop target DB name
        maintenance_config['database'] = 'postgres'      # Connect to default DB
        
        pg_maintenance_conn = psycopg2.connect(**maintenance_config)
        pg_maintenance_conn.autocommit = True  # CREATE DATABASE cannot run inside a transaction
        maint_cursor = pg_maintenance_conn.cursor()
        
        maint_cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db_name,))
        if not maint_cursor.fetchone():
            print(f"Database '{target_db_name}' does not exist. Creating it...")
            # Use psycopg2's sql module for safe identifier quoting
            maint_cursor.execute(f"CREATE DATABASE {quote_identifier(target_db_name)}")
            print("Database created successfully.")
        else:
            print(f"Database '{target_db_name}' already exists.")
        
        maint_cursor.close()
        print("--- Step 0: Complete. ---\n")

    except psycopg2.Error as err:
        print(f"PostgreSQL connection error during database creation: {err}", file=sys.stderr)
        sys.exit(1)
    finally:
        if pg_maintenance_conn:
            pg_maintenance_conn.close()
    # --- End of Step 0 ---

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

        if not tables:
            print("No tables found to truncate. Skipping.")
        else:
            for table_name in tables:
                try:
                    print(f"Truncating table: {table_name}...")
                    pg_cursor.execute(f"TRUNCATE TABLE {quote_identifier(table_name)} RESTART IDENTITY CASCADE")
                    print(f"Table {table_name} truncated successfully.")
                except Exception as e:
                    print(f"Could not truncate table {table_name}. Reason: {e}", file=sys.stderr)
                    pg_conn.rollback()
        
        pg_conn.commit()
        print("--- Step 1: Truncation complete. ---")
        print()

    except psycopg2.Error as err:
        print(f"PostgreSQL connection error during truncation: {err}", file=sys.stderr)
        # If the error is that the database doesn't exist, the new logic should have handled it.
        # Any other error here is a problem.
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
        
        # --- FIX: Create ALL tables before migration ---
        print("Ensuring all tables exist in PostgreSQL...")
        pg_cursor_fix = postgres_conn.cursor()

        all_create_sqls = [
            """CREATE TABLE IF NOT EXISTS admin (
                admin_id SERIAL PRIMARY KEY, account VARCHAR(50) NOT NULL DEFAULT '', password VARCHAR(200) NOT NULL DEFAULT '', email VARCHAR(50) NOT NULL DEFAULT '', display_name VARCHAR(50) NOT NULL DEFAULT '', roles VARCHAR(200) NOT NULL DEFAULT '', update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, enable VARCHAR(22) NOT NULL DEFAULT 'yes'
            );""",
            """CREATE TABLE IF NOT EXISTS album (
                album_id SERIAL PRIMARY KEY, title VARCHAR(100) NOT NULL DEFAULT '', url VARCHAR(1000) NOT NULL DEFAULT '', cover_asset_code VARCHAR(100) NOT NULL DEFAULT '', update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, enable VARCHAR(22) NOT NULL DEFAULT 'yes'
            );""",
            """CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY, sys VARCHAR(22) NOT NULL, tcf_type VARCHAR(22) NOT NULL, api_key VARCHAR(500) NOT NULL, updated_at TIMESTAMP NULL DEFAULT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS api_logs (
                id SERIAL PRIMARY KEY, sys VARCHAR(22) NULL DEFAULT NULL, action VARCHAR(100) NOT NULL, url TEXT NOT NULL, from_ip VARCHAR(100) NOT NULL, from_agent TEXT NULL DEFAULT NULL, request_content TEXT NULL DEFAULT NULL, reply_status VARCHAR(22) NULL DEFAULT NULL, note TEXT NULL DEFAULT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS apply_meta (
                apply_meta_id SERIAL PRIMARY KEY, sn VARCHAR(50) NOT NULL DEFAULT '', order_uid VARCHAR(200) NULL DEFAULT NULL, account VARCHAR(50) NOT NULL DEFAULT '', name VARCHAR(22) NOT NULL DEFAULT '', email VARCHAR(50) NOT NULL DEFAULT '', tel VARCHAR(50) NOT NULL DEFAULT '', area VARCHAR(22) NOT NULL DEFAULT '', area_other TEXT NOT NULL, volunteer_belong VARCHAR(22) NOT NULL DEFAULT '', purpose TEXT NULL DEFAULT NULL, purpose_other TEXT NOT NULL, review_admin_id INTEGER NOT NULL DEFAULT 0, review_opinion TEXT NOT NULL, status VARCHAR(22) NOT NULL, download_file_name VARCHAR(100) NULL DEFAULT NULL, expire_date TIMESTAMP NULL DEFAULT NULL, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, enable VARCHAR(22) NOT NULL DEFAULT 'yes'
            );""",
            """CREATE TABLE IF NOT EXISTS apply_meta_assets (
                apply_meta_assets_id SERIAL PRIMARY KEY, apply_meta_id INTEGER NULL DEFAULT NULL, order_uid VARCHAR(100) NULL DEFAULT NULL, asset_id VARCHAR(200) NULL DEFAULT '', ItemCode VARCHAR(200) NULL DEFAULT NULL, xx_file_name VARCHAR(200) NULL DEFAULT NULL, available_status VARCHAR(100) NOT NULL, reject_reason TEXT NOT NULL, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, enable VARCHAR(22) NOT NULL DEFAULT 'yes'
            );""",
            """CREATE TABLE IF NOT EXISTS asset (
                asset_id SERIAL PRIMARY KEY, tcf_source VARCHAR(200) NOT NULL, tcf_type VARCHAR(100) NULL DEFAULT NULL, ItemCode VARCHAR(200) NOT NULL, PackageName VARCHAR(500) NULL DEFAULT NULL, state_id INTEGER NULL DEFAULT NULL, TitleType VARCHAR(50) NULL DEFAULT NULL, category VARCHAR(100) NULL DEFAULT NULL, EventName VARCHAR(500) NULL DEFAULT NULL, StoryTitle VARCHAR(500) NOT NULL, FilmDescription TEXT NULL DEFAULT NULL, FilmCharactor VARCHAR(100) NULL DEFAULT NULL, EventDateStart TIMESTAMP NULL DEFAULT NULL, EventDateEnd TIMESTAMP NULL DEFAULT NULL, Affiliates VARCHAR(200) NULL DEFAULT NULL, Location VARCHAR(200) NULL DEFAULT NULL, LocationOther VARCHAR(200) NULL DEFAULT NULL, OldPlace VARCHAR(200) NOT NULL, "xx-keyword-" TEXT NULL DEFAULT NULL, Photographer VARCHAR(50) NULL DEFAULT NULL, Provider VARCHAR(100) NULL DEFAULT NULL, BookTitle VARCHAR(100) NOT NULL, PublicationInfo VARCHAR(100) NULL DEFAULT NULL, Copyright VARCHAR(100) NULL DEFAULT NULL, FilmID VARCHAR(100) NULL DEFAULT NULL, AccessLevel VARCHAR(22) NULL DEFAULT NULL, ShootingDate VARCHAR(50) NULL DEFAULT NULL, CameraManufacturer VARCHAR(50) NULL DEFAULT NULL, CameraModel VARCHAR(50) NULL DEFAULT NULL, ResolutionWide VARCHAR(22) NULL DEFAULT NULL, ResolutionHigh INTEGER NULL DEFAULT NULL, FileSize VARCHAR(22) NULL DEFAULT NULL, Ratings VARCHAR(22) NULL DEFAULT NULL, CuratorialLabel VARCHAR(500) NULL DEFAULT NULL, DocumentType VARCHAR(50) NOT NULL, PublishQuantity VARCHAR(100) NULL DEFAULT NULL, ChapterTitle VARCHAR(200) NULL DEFAULT NULL, Publisher VARCHAR(100) NULL DEFAULT NULL, PublishAuthor VARCHAR(50) NULL DEFAULT NULL, StorySummary TEXT NULL DEFAULT NULL, StoryContents TEXT NULL DEFAULT NULL, PublicDate TIMESTAMP NULL DEFAULT NULL, MainLanguage VARCHAR(22) NULL DEFAULT NULL, PageNumber VARCHAR(22) NULL DEFAULT NULL, originalFilename VARCHAR(300) NULL DEFAULT NULL, state1 VARCHAR(50) NULL DEFAULT NULL, state2 VARCHAR(50) NULL DEFAULT NULL, Missions VARCHAR(500) NOT NULL, Dateone TIMESTAMP NULL DEFAULT NULL, Contents TEXT NULL DEFAULT NULL, ProjectTitle VARCHAR(300) NULL DEFAULT NULL, Erratanotes TEXT NULL DEFAULT NULL, WebTitle VARCHAR(100) NULL DEFAULT NULL, WebUrl VARCHAR(500) NULL DEFAULT NULL, WebSiteCode VARCHAR(50) NULL DEFAULT NULL, WebVideoUrl VARCHAR(500) NULL DEFAULT NULL, WebEditor VARCHAR(50) NULL DEFAULT NULL, TitleLastUpdate TIMESTAMP NULL DEFAULT NULL, deleteDate TIMESTAMP NULL DEFAULT NULL, updated_at TIMESTAMP NULL DEFAULT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS asset_file (
                asset_file_id SERIAL PRIMARY KEY, ItemCode VARCHAR(200) NOT NULL, file_name VARCHAR(200) NOT NULL, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS asset_keywords (
                asset_keyword_id SERIAL PRIMARY KEY, ItemCode VARCHAR(100) NOT NULL, Keyword_Formal VARCHAR(100) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS asset_logs (
                asset_log_id SERIAL PRIMARY KEY, source VARCHAR(22) NOT NULL, user_id INTEGER NULL DEFAULT NULL, api_sys VARCHAR(22) NULL DEFAULT NULL, api_key VARCHAR(250) NULL DEFAULT NULL, tcf_type VARCHAR(22) NOT NULL, ItemCode VARCHAR(50) NOT NULL, operate_type VARCHAR(22) NOT NULL, content TEXT NOT NULL, ip VARCHAR(50) NOT NULL, user_agent TEXT NOT NULL, updated_at TIMESTAMP NULL DEFAULT NULL, logged_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS attachment (
                attachment_id SERIAL PRIMARY KEY, title VARCHAR(50) NOT NULL DEFAULT '', file_name VARCHAR(50) NOT NULL DEFAULT '', update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS errata (
                errata_id SERIAL PRIMARY KEY, sn VARCHAR(100) NOT NULL DEFAULT '', ItemCode VARCHAR(200) NOT NULL, account VARCHAR(50) NOT NULL DEFAULT '', name VARCHAR(22) NOT NULL DEFAULT '', email VARCHAR(50) NOT NULL DEFAULT '', tel VARCHAR(50) NOT NULL DEFAULT '', area VARCHAR(22) NOT NULL DEFAULT '', volunteer_belong VARCHAR(22) NOT NULL DEFAULT '', opinion TEXT NULL DEFAULT NULL, status VARCHAR(22) NOT NULL, process_note TEXT NOT NULL, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, enable VARCHAR(22) NOT NULL DEFAULT 'yes'
            );""",
            """CREATE TABLE IF NOT EXISTS feedback (
                feedback_id SERIAL PRIMARY KEY, account VARCHAR(50) NOT NULL DEFAULT '', name VARCHAR(22) NOT NULL DEFAULT '', email VARCHAR(50) NOT NULL DEFAULT '', tel VARCHAR(50) NOT NULL DEFAULT '', opinion TEXT NULL DEFAULT NULL, process_note TEXT NOT NULL, status VARCHAR(50) NOT NULL, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, enable VARCHAR(22) NOT NULL DEFAULT 'yes'
            );""",
            """CREATE TABLE IF NOT EXISTS hot_keyword (
                hot_keyword_id SERIAL PRIMARY KEY, keyword VARCHAR(22) NOT NULL DEFAULT '', pos INTEGER NOT NULL DEFAULT 0, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS log_api_called (
                log_api_called_id SERIAL PRIMARY KEY, order_uid VARCHAR(100) NOT NULL, action VARCHAR(100) NOT NULL, url TEXT NULL DEFAULT NULL, from_ip VARCHAR(100) NOT NULL, from_agent TEXT NULL DEFAULT NULL, request_content TEXT NULL DEFAULT NULL, reply_content TEXT NULL DEFAULT NULL, status VARCHAR(50) NOT NULL, note TEXT NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS manual (
                manual_id SERIAL PRIMARY KEY, title VARCHAR(22) NOT NULL DEFAULT '', content TEXT NULL DEFAULT NULL, pos INTEGER NOT NULL DEFAULT 0, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS news (
                news_id SERIAL PRIMARY KEY, title VARCHAR(50) NOT NULL DEFAULT '', content TEXT NOT NULL, pos INTEGER NOT NULL DEFAULT 0, is_carousel VARCHAR(22) NOT NULL DEFAULT 'no', feature_image VARCHAR(200) NULL DEFAULT NULL, icon VARCHAR(22) NOT NULL DEFAULT '', publish_date TIMESTAMP NULL DEFAULT NULL, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS qna (
                qna_id SERIAL PRIMARY KEY, question VARCHAR(100) NOT NULL DEFAULT '', answer TEXT NULL DEFAULT NULL, pos INTEGER NOT NULL, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS rcd_asset_browse (
                rcd_browse_id SERIAL PRIMARY KEY, account VARCHAR(50) NOT NULL DEFAULT '', ItemCode VARCHAR(100) NOT NULL, tcf_type VARCHAR(22) NOT NULL DEFAULT '', ip VARCHAR(100) NULL DEFAULT NULL, agent VARCHAR(200) NULL DEFAULT NULL, browse_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS rcd_keyword (
                rcd_keyword_id SERIAL PRIMARY KEY, account VARCHAR(50) NOT NULL, category VARCHAR(22) NOT NULL, keyword VARCHAR(50) NOT NULL DEFAULT '', ip VARCHAR(100) NOT NULL, agent VARCHAR(500) NOT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS rcd_login (
                rcd_login_id SERIAL PRIMARY KEY, account VARCHAR(50) NOT NULL DEFAULT '', ldap VARCHAR(100) NULL DEFAULT NULL, result VARCHAR(22) NOT NULL DEFAULT '', login_date TIMESTAMP NOT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );""",
            """CREATE TABLE IF NOT EXISTS setting (
                setting_id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL, value TEXT NOT NULL
            );""",
            """CREATE TABLE IF NOT EXISTS "user" (
                user_id SERIAL PRIMARY KEY, account VARCHAR(50) NOT NULL, ldap VARCHAR(50) NOT NULL, name VARCHAR(100) NOT NULL, area VARCHAR(50) NOT NULL DEFAULT '', volunteer_belong VARCHAR(100) NOT NULL DEFAULT '', email VARCHAR(100) NOT NULL, tel VARCHAR(100) NOT NULL, update_date TIMESTAMP NULL DEFAULT NULL, create_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, enable VARCHAR(50) NOT NULL DEFAULT 'yes'
            );""",
            """CREATE TABLE IF NOT EXISTS website_code (
                website_code_id SERIAL PRIMARY KEY, code VARCHAR(50) NOT NULL, name VARCHAR(100) NOT NULL
            );"""
        ]

        for create_sql in all_create_sqls:
            try:
                pg_cursor_fix.execute(create_sql)
            except Exception as e:
                print(f"Error executing CREATE TABLE: {e}")
                print(f"Failed SQL: {create_sql}")
                postgres_conn.rollback()
                raise e

        postgres_conn.commit()
        pg_cursor_fix.close()
        print("All table schemas are ready.")
        # --- END FIX ---

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