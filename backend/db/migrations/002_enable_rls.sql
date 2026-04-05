-- ── 002_enable_rls.sql ────────────────────────────────────────────────────────
-- Run AFTER 001_create_tables.sql.
-- ──────────────────────────────────────────────────────────────────────────────

-- ── favorites ─────────────────────────────────────────────────────────────────
ALTER TABLE public.favorites ENABLE ROW LEVEL SECURITY;

-- 用戶只能讀取自己的最愛
CREATE POLICY "favorites: owner can select"
    ON public.favorites
    FOR SELECT
    USING (auth.uid() = user_id);

-- 用戶只能新增屬於自己的資料
CREATE POLICY "favorites: owner can insert"
    ON public.favorites
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- 用戶只能刪除自己的資料
CREATE POLICY "favorites: owner can delete"
    ON public.favorites
    FOR DELETE
    USING (auth.uid() = user_id);

-- ── ai_recommendations ────────────────────────────────────────────────────────
ALTER TABLE public.ai_recommendations ENABLE ROW LEVEL SECURITY;

-- 所有已登入用戶可讀
CREATE POLICY "ai_recommendations: authenticated can select"
    ON public.ai_recommendations
    FOR SELECT
    USING (auth.role() = 'authenticated');

-- 只有 service_role 可寫（INSERT / UPDATE / DELETE）
-- service_role 會繞過 RLS，因此不需要額外 policy；
-- 以下 policy 明確拒絕非 service_role 的寫入，作為防禦性設定。
CREATE POLICY "ai_recommendations: deny non-service write"
    ON public.ai_recommendations
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- ── stock_cache ────────────────────────────────────────────────────────────────
ALTER TABLE public.stock_cache ENABLE ROW LEVEL SECURITY;

-- 所有人（含未登入）可讀
CREATE POLICY "stock_cache: public can select"
    ON public.stock_cache
    FOR SELECT
    USING (true);

-- 只有 service_role 可寫（同上，防禦性設定）
CREATE POLICY "stock_cache: deny non-service write"
    ON public.stock_cache
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
