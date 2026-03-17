-- Run once in Supabase SQL Editor. Stores color quiz result (and later other profile fields).
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id UUID PRIMARY KEY,
    color_season VARCHAR(50),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Allow anon to read/upsert for MVP (same default user as wardrobe).
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all for anon" ON user_profiles
    FOR ALL
    USING (true)
    WITH CHECK (true);
