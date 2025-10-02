from fastapi import FastAPI
from typing import List
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Vector Search API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Vector Search API"}

@app.get("/search")
def search_items(keyword: str):
    # For now, return a fixed list of dummy data to solve the 404 error.
    # The real implementation will query the database.
    print(f"Received search query: {keyword}")
    return [
        {"id": 1, "content": f"Dummy result for: {keyword} 1", "score": 0.98},
        {"id": 2, "content": "This is a hardcoded search result.", "score": 0.95},
        {"id": 3, "content": "The real implementation is pending.", "score": 0.92}
    ]
