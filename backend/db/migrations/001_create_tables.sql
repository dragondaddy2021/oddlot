-- ── 001_create_tables.sql ─────────────────────────────────────────────────────
-- Run this first in Supabase Dashboard > SQL Editor.
-- ──────────────────────────────────────────────────────────────────────────────

-- ── 1. favorites（我的最愛）────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.favorites (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID         NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    stock_symbol VARCHAR(10)  NOT NULL,
    stock_name   VARCHAR(50)  NOT NULL,
    added_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT favorites_user_symbol_unique UNIQUE (user_id, stock_symbol)
);

-- ── 2. ai_recommendations（每日 AI 選股結果）──────────────────────────────────
CREATE TABLE IF NOT EXISTS public.ai_recommendations (
    id         UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    date       DATE    NOT NULL UNIQUE,
    stocks     JSONB   NOT NULL,
    reasoning  TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 3. stock_cache（股票資料快取）─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.stock_cache (
    symbol     VARCHAR(10)    PRIMARY KEY,
    name       VARCHAR(50)    NOT NULL,
    price      NUMERIC(10, 2),
    yield_rate NUMERIC(5,  2),
    pe_ratio   NUMERIC(8,  2),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
