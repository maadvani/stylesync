-- Run once in Supabase SQL Editor to support Daily Trend Intelligence MVP.
-- Creates:
--  - trends: clustered trend records
--  - user_trend_matches: cached matches per user (optional but matches PRD schema)

CREATE TABLE IF NOT EXISTS trends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    keywords TEXT[],
    dominant_colors TEXT[],
    size INTEGER DEFAULT 0,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    velocity FLOAT DEFAULT 0,
    cluster_id INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trends_cluster_id ON trends(cluster_id);

CREATE TABLE IF NOT EXISTS user_trend_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    trend_id UUID NOT NULL REFERENCES trends(id) ON DELETE CASCADE,
    match_score FLOAT DEFAULT 0,
    wardrobe_coverage FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, trend_id)
);

-- Allow anon to read/write for MVP. (For later auth, we tighten RLS.)
ALTER TABLE trends ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_trend_matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all for anon - trends" ON trends
    FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Allow all for anon - user_trend_matches" ON user_trend_matches
    FOR ALL
    USING (true)
    WITH CHECK (true);

