from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import psycopg2.extras

app = FastAPI(title="Vector Search API")

# Add CORS middleware to allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# PostgreSQL connection details
POSTGRES_CONFIG = {
    'host': 'postgres', # Use the service name from docker-compose
    'port': 5432,
    'user': 'user',
    'password': 'password',
    'database': 'tc_search_v15'
}

@app.get("/")
def read_root():
    return {"message": "Welcome to the Vector Search API"}

def perform_search(keyword: str) -> List[Dict[str, Any]]:
    """Core search logic, reusable by multiple endpoints."""
    conn = None
    try:
        conn = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        select_columns = [
            "asset_id", "eventname", "storytitle", 
            "storycontents", "category", "filmdescription"
        ]
        search_columns = [
            "eventname", "storytitle", "storycontents", 
            "category", "filmdescription"
        ]

        # Use lowercase column names without quotes for the query
        where_clause = " OR ".join([f'{col} ILIKE %s' for col in search_columns])
        query = f'SELECT {", ".join(select_columns)} FROM asset WHERE {where_clause} ORDER BY created_at DESC LIMIT 100;'
        params = (f'%{keyword}%',) * len(search_columns)

        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        return results

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/search", response_model=List[Dict[str, Any]])
def search_items(keyword: str):
    """Endpoint for general search, called by the frontend."""
    if not keyword:
        return []
    return perform_search(keyword)