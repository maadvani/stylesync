-- Run in Supabase SQL editor.
CREATE TABLE IF NOT EXISTS wear_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    worn_on DATE NOT NULL DEFAULT CURRENT_DATE,
    item_ids TEXT[] NOT NULL,
    source TEXT NOT NULL DEFAULT 'outfit_card',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wear_logs_user_on ON wear_logs(user_id, worn_on DESC);

ALTER TABLE wear_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all for anon wear logs" ON wear_logs
    FOR ALL
    USING (true)
    WITH CHECK (true);

