
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any

# PostgreSQL connection details
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'user': 'postgres',
    'password': 'tc94800552',
    'database': 'tc_search_v15'  # Changed to tc_search_v15
}

app = FastAPI()

# CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"]  # Allows all origins
)

class SearchResult(BaseModel):
    asset_id: int
    TitleType: str | None = None
    FilmDescription: str | None = None
    WebUrl: str | None = None
    created_at: str | None = None
    PackageName: str | None = None
    EventName: str | None = None
    StoryTitle: str | None = None
    StorySummary: str | None = None
    StoryContents: str | None = None
    WebTitle: str | None = None

@app.get("/search", response_model=List[Dict[str, Any]])
def search(keyword: str):
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Expanded search to include more text-based columns
        query = """
            SELECT
                "asset_id", "TitleType", "FilmDescription", "WebUrl", "created_at",
                "PackageName", "EventName", "StoryTitle", "StorySummary", "StoryContents",
                "WebTitle"
            FROM asset
            WHERE
                "TitleType" ILIKE %s OR "FilmDescription" ILIKE %s OR
                "PackageName" ILIKE %s OR "EventName" ILIKE %s OR
                "StoryTitle" ILIKE %s OR "StorySummary" ILIKE %s OR
                "StoryContents" ILIKE %s OR "WebTitle" ILIKE %s;
        """
        search_keyword = f"%{keyword}%"
        # 8 parameters for the 8 columns in the WHERE clause
        params = [search_keyword] * 8

        cur.execute(query, params)
        
        rows = cur.fetchall()
        
        # Get column names from cursor description
        column_names = [desc[0] for desc in cur.description]
        
        results = [dict(zip(column_names, row)) for row in rows]
        
        return results

    except psycopg2.Error as err:
        # Return a JSON response with the error message
        return [{"error": f"Database query failed: {err}"}]
    except Exception as e:
        # Return a JSON response for other errors
        return [{"error": f"An unexpected error occurred: {e}"}]
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
