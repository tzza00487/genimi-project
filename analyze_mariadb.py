import mysql.connector

# MariaDB connection details
DB_CONFIG = {
    'host': '127.0.0.1',  # MariaDB container is mapped to localhost
    'port': 3306,
    'user': 'root',
    'password': 'tc94800552',
}

def analyze_mariadb():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        print("Connected to MariaDB successfully!")

        # List databases
        cursor.execute("SHOW DATABASES")
        databases = [db[0] for db in cursor.fetchall()]
        print("\nDatabases in MariaDB:")
        for db in databases:
            print(f"- {db}")

        # For each database, list tables and get row count
        for db in databases:
            if db not in ['information_schema', 'mysql', 'performance_schema', 'sys']: # Skip system databases
                print(f"\n--- Tables in database: {db} ---")
                cursor.execute(f"USE {db}")
                cursor.execute("SHOW TABLES")
                tables = [table[0] for table in cursor.fetchall()]
                if tables:
                    for table in tables:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        row_count = cursor.fetchone()[0]
                        print(f"  - Table: {table}, Rows: {row_count}")
                        # Fetch first 5 rows as sample data
                        cursor.execute(f"SELECT * FROM {table} LIMIT 5")
                        columns = [col[0] for col in cursor.description]
                        sample_data = cursor.fetchall()
                        if sample_data:
                            print(f"    Sample Data (first 5 rows) for {table}:")
                            print(f"    Columns: {columns}")
                            for row in sample_data:
                                print(f"    {row}")
                        else:
                            print(f"    No sample data for {table} (table is empty or has less than 5 rows).")
                else:
                    print(f"  No tables found in database: {db}")

    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            print("\nMariaDB connection closed.")

if __name__ == "__main__":
    analyze_mariadb()
