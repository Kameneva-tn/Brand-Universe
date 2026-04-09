-- Виконай цей SQL в Supabase → SQL Editor
-- Створює таблиці для Моніторинг-агента

-- 1. Пости конкурентів
CREATE TABLE IF NOT EXISTS competitor_posts (
  id              BIGSERIAL PRIMARY KEY,
  platform        TEXT NOT NULL,          -- instagram | facebook | threads
  post_id         TEXT NOT NULL,
  username        TEXT NOT NULL,
  post_type       TEXT,                   -- image | video | reel | carousel | text
  caption         TEXT,
  likes           INTEGER DEFAULT 0,
  comments        INTEGER DEFAULT 0,
  views           INTEGER DEFAULT 0,
  shares          INTEGER DEFAULT 0,
  engagement_rate FLOAT DEFAULT 0,
  engagement_score FLOAT DEFAULT 0,       -- нормалізований 0-100
  content_type    TEXT,                   -- educational | promotional | lifestyle | ...
  hashtags        TEXT[] DEFAULT '{}',
  url             TEXT,
  thumbnail_url   TEXT,
  posted_at       TIMESTAMPTZ,
  collected_at    TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(platform, post_id)
);

-- 2. Агреговані метрики по акаунту за день
CREATE TABLE IF NOT EXISTS competitor_metrics (
  id                    BIGSERIAL PRIMARY KEY,
  platform              TEXT NOT NULL,
  username              TEXT NOT NULL,
  date                  DATE NOT NULL,
  posts_count           INTEGER DEFAULT 0,
  avg_engagement_rate   FLOAT DEFAULT 0,
  max_engagement_rate   FLOAT DEFAULT 0,
  total_likes           INTEGER DEFAULT 0,
  total_comments        INTEGER DEFAULT 0,
  total_views           INTEGER DEFAULT 0,
  best_hour             INTEGER,
  best_day              TEXT,
  posts_per_week        FLOAT,
  top_content_type      TEXT,
  created_at            TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(platform, username, date)
);

-- 3. ML Інсайти (аномалії, тренди, AI-висновки)
CREATE TABLE IF NOT EXISTS ml_insights (
  id            BIGSERIAL PRIMARY KEY,
  brand_id      TEXT DEFAULT 'default',
  insight_type  TEXT NOT NULL,           -- anomaly | trend | ai_summary | pattern
  platform      TEXT,
  username      TEXT,
  title         TEXT NOT NULL,
  body          TEXT,
  url           TEXT,
  score         FLOAT DEFAULT 0,
  is_read       BOOLEAN DEFAULT FALSE,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Індекси для швидкого читання дашборду
CREATE INDEX IF NOT EXISTS idx_posts_platform_username ON competitor_posts(platform, username);
CREATE INDEX IF NOT EXISTS idx_posts_posted_at ON competitor_posts(posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_date ON competitor_metrics(date DESC);
CREATE INDEX IF NOT EXISTS idx_insights_created ON ml_insights(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_insights_brand ON ml_insights(brand_id, created_at DESC);

-- RLS: дозволяємо читання з Lovable (anon key)
ALTER TABLE competitor_posts   ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitor_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE ml_insights        ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read" ON competitor_posts   FOR SELECT USING (true);
CREATE POLICY "Public read" ON competitor_metrics FOR SELECT USING (true);
CREATE POLICY "Public read" ON ml_insights        FOR SELECT USING (true);

-- Service role може писати (Python агент використовує service key)
CREATE POLICY "Service write posts"   ON competitor_posts   FOR ALL USING (true);
CREATE POLICY "Service write metrics" ON competitor_metrics FOR ALL USING (true);
CREATE POLICY "Service write insights" ON ml_insights       FOR ALL USING (true);
