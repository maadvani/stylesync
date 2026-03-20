"""
StyleSync API – wardrobe upload pipeline.
Upload image → Cloudinary → HF caption → Groq JSON → Supabase → return item.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import wardrobe, user as user_router, utility as utility_router, trends as trends_router

app = FastAPI(
    title="StyleSync API",
    description="Wardrobe digitization: upload, AI tagging, storage.",
    version="0.1.0",
)

# Allow any localhost port so the frontend can reach the API (Vite default 5173, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wardrobe.router, prefix="/api")
app.include_router(user_router.router, prefix="/api")
app.include_router(utility_router.router, prefix="/api")
app.include_router(trends_router.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
