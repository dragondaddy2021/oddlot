-- ── 004_create_custom_etfs.sql ────────────────────────────────────────────────
-- 自組 ETF 功能（custom_etfs + custom_etf_stocks）
-- Run this in Supabase Dashboard > SQL Editor.
-- ──────────────────────────────────────────────────────────────────────────────

-- ── 1. custom_etfs（使用者自組 ETF 主表）──────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.custom_etfs (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID         NOT NULL,
    etf_name    VARCHAR(50)  NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- ── 2. custom_etf_stocks（ETF 成分股）─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.custom_etf_stocks (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    etf_id       UUID         NOT NULL REFERENCES public.custom_etfs (id) ON DELETE CASCADE,
    stock_symbol VARCHAR(10)  NOT NULL,
    stock_name   VARCHAR(50)  NOT NULL,
    weight       NUMERIC(5,2) DEFAULT 0,
    added_at     TIMESTAMPTZ  DEFAULT NOW(),

    CONSTRAINT custom_etf_stocks_etf_symbol_unique UNIQUE (etf_id, stock_symbol)
);

-- ── 3. Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE public.custom_etfs       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.custom_etf_stocks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users manage own etfs"
    ON public.custom_etfs
    FOR ALL
    TO authenticated
    USING      (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users manage own etf stocks"
    ON public.custom_etf_stocks
    FOR ALL
    TO authenticated
    USING (EXISTS (
        SELECT 1
        FROM public.custom_etfs
        WHERE public.custom_etfs.id      = public.custom_etf_stocks.etf_id
          AND public.custom_etfs.user_id = auth.uid()
    ));
