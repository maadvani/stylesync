-- Run in Supabase SQL Editor: candidate purchases to score against the user's wardrobe.
-- StyleSync Shopping page reads this table and runs UtilityScorer on each row.

CREATE TABLE IF NOT EXISTS shopping_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL,
    primary_color VARCHAR(50),
    secondary_color VARCHAR(50),
    pattern VARCHAR(50),
    formality INTEGER CHECK (formality BETWEEN 1 AND 5) DEFAULT 3,
    seasons TEXT[],
    material VARCHAR(80),
    style_tags TEXT[],
    price NUMERIC(12, 2),
    link TEXT,
    image_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Backward-compatible for already-created tables.
ALTER TABLE shopping_recommendations
    ADD COLUMN IF NOT EXISTS link TEXT;

CREATE INDEX IF NOT EXISTS idx_shopping_recommendations_user_id ON shopping_recommendations(user_id);
CREATE INDEX IF NOT EXISTS idx_shopping_recommendations_created_at ON shopping_recommendations(created_at DESC);

ALTER TABLE shopping_recommendations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow all for anon shopping_recommendations" ON shopping_recommendations;

CREATE POLICY "Allow all for anon shopping_recommendations" ON shopping_recommendations
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Optional demo rows (same default user as wardrobe MVP):
-- INSERT INTO shopping_recommendations (user_id, name, type, primary_color, pattern, formality, seasons, price)
-- VALUES
--   ('00000000-0000-0000-0000-000000000001', 'Camel wool blazer', 'blazer', 'camel', 'solid', 4, ARRAY['fall','winter'], 180),
--   ('00000000-0000-0000-0000-000000000001', 'Satin hot-pink mini dress', 'dress', 'hot pink', 'solid', 4, ARRAY['spring','summer'], 140),
--   ('00000000-0000-0000-0000-000000000001', 'Cream wide-leg trousers', 'pants', 'cream', 'solid', 3, ARRAY['spring','summer','fall'], 110);
