-- ── 003_create_indexes.sql ────────────────────────────────────────────────────
-- Run AFTER 002_enable_rls.sql.
-- ──────────────────────────────────────────────────────────────────────────────

-- ── favorites ─────────────────────────────────────────────────────────────────
-- 快速查詢某用戶的所有最愛
CREATE INDEX IF NOT EXISTS idx_favorites_user_id
    ON public.favorites (user_id);

-- 快速查詢特定股票被哪些用戶收藏
CREATE INDEX IF NOT EXISTS idx_favorites_stock_symbol
    ON public.favorites (stock_symbol);

-- ── ai_recommendations ────────────────────────────────────────────────────────
-- 快速依日期查詢當日選股結果
CREATE INDEX IF NOT EXISTS idx_ai_recommendations_date
    ON public.ai_recommendations (date DESC);

-- ── stock_cache ────────────────────────────────────────────────────────────────
-- 快速找出最舊（需要更新）的快取資料
CREATE INDEX IF NOT EXISTS idx_stock_cache_updated_at
    ON public.stock_cache (updated_at ASC);
