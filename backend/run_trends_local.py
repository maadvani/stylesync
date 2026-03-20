"""
Local manual run for Daily Trend Intelligence MVP.

Run from project root:
  cd backend
  python run_trends_local.py

It will:
  - scrape a small set of sources
  - extract trend candidates with Groq (JSON-only)
  - cluster candidates with local embeddings + HDBSCAN
  - store clustered trends in Supabase

Then your frontend can call:
  GET /api/trends
"""

from __future__ import annotations

from services.trends_pipeline import run_scrape_and_store_trends, DEFAULT_SOURCES


def main() -> None:
    print("Running local trend scrape + clustering…")
    stored = run_scrape_and_store_trends(sources=DEFAULT_SOURCES)
    print(f"Stored {len(stored)} clustered trends in Supabase.")
    for t in stored[:5]:
        print("-", t.get("name"))


if __name__ == "__main__":
    main()

