-- Run this in Supabase SQL Editor (Dashboard → SQL Editor) to create the wardrobe_items table.
-- StyleSync PRD schema; one row per uploaded clothing item.

CREATE TABLE IF NOT EXISTS wardrobe_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    image_url TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    primary_color VARCHAR(50),
    secondary_color VARCHAR(50),
    pattern VARCHAR(50),
    formality INTEGER CHECK (formality BETWEEN 1 AND 5),
    seasons TEXT[],
    material VARCHAR(50),
    style_tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wardrobe_items_user_id ON wardrobe_items(user_id);

-- Optional: allow anonymous inserts (for MVP without auth). Adjust RLS as needed.
ALTER TABLE wardrobe_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all for anon" ON wardrobe_items
    FOR ALL
    USING (true)
    WITH CHECK (true);
