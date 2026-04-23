import { useEffect, useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { supabase } from "../lib/supabase";

export default function MyETFs() {
  const { user, loading: authLoading } = useAuth();
  const [etfs, setEtfs] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    Promise.all([
      supabase
        .from("custom_etfs")
        .select("*, custom_etf_stocks(*)")
        .eq("user_id", user.id)
        .order("created_at", { ascending: false }),
      supabase
        .from("favorites")
        .select("*")
        .eq("user_id", user.id)
        .order("added_at", { ascending: false }),
    ])
      .then(([etfsRes, favRes]) => {
        if (etfsRes.error) {
          setError("ETF 清單載入失敗，請重新整理。");
        } else {
          setEtfs(etfsRes.data ?? []);
        }
        if (!favRes.error) setFavorites(favRes.data ?? []);
      })
      .finally(() => setLoading(false));
  }, [user]);

  const handleCreate = async (e) => {
    e.preventDefault();
    const name = formName.trim();
    if (!name) return;
    setCreating(true);
    const { data, error: err } = await supabase
      .from("custom_etfs")
      .insert({
        user_id: user.id,
        etf_name: name,
        description: formDesc.trim() || null,
      })
      .select()
      .single();
    setCreating(false);
    if (err) {
      alert("建立失敗，請稍後再試");
      return;
    }
    setEtfs([{ ...data, custom_etf_stocks: [] }, ...etfs]);
    setFormName("");
    setFormDesc("");
    setShowForm(false);
  };

  const handleDeleteETF = async (id) => {
    if (!confirm("確定要刪除此 ETF？成分股與設定將一併移除。")) return;
    await supabase.from("custom_etfs").delete().eq("id", id);
    setEtfs(etfs.filter((e) => e.id !== id));
  };

  const handleAddStock = async (etfId, fav) => {
    const { data, error: err } = await supabase
      .from("custom_etf_stocks")
      .insert({
        etf_id: etfId,
        stock_symbol: fav.stock_symbol,
        stock_name: fav.stock_name,
        weight: 0,
      })
      .select()
      .single();
    if (err) return;
    setEtfs(
      etfs.map((e) =>
        e.id === etfId
          ? { ...e, custom_etf_stocks: [...(e.custom_etf_stocks ?? []), data] }
          : e,
      ),
    );
  };

  const handleUpdateWeight = async (etfId, stockId, weight) => {
    await supabase.from("custom_etf_stocks").update({ weight }).eq("id", stockId);
    setEtfs(
      etfs.map((e) =>
        e.id === etfId
          ? {
              ...e,
              custom_etf_stocks: e.custom_etf_stocks.map((s) =>
                s.id === stockId ? { ...s, weight } : s,
              ),
            }
          : e,
      ),
    );
  };

  const handleRemoveStock = async (etfId, stockId) => {
    await supabase.from("custom_etf_stocks").delete().eq("id", stockId);
    setEtfs(
      etfs.map((e) =>
        e.id === etfId
          ? { ...e, custom_etf_stocks: e.custom_etf_stocks.filter((s) => s.id !== stockId) }
          : e,
      ),
    );
  };

  if (authLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-5xl mb-4">🔒</p>
          <h2 className="text-xl font-bold text-gray-800 mb-2">此功能需要登入，敬請期待</h2>
          <p className="text-gray-500 text-sm">登入開放後即可自組個人化 ETF 投資組合</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6 gap-3">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">我的 ETF</h2>
            <p className="text-gray-500 text-sm mt-1">自組個人化投資組合，從我的最愛挑選成分股</p>
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-xl text-sm font-medium transition-colors shrink-0"
          >
            {showForm ? "取消" : "＋ 新增 ETF"}
          </button>
        </div>

        {showForm && (
          <form
            onSubmit={handleCreate}
            className="bg-white rounded-2xl border border-gray-100 shadow-sm p-5 mb-6 space-y-3"
          >
            <input
              type="text"
              placeholder="ETF 名稱（例：我的高股息）"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              maxLength={50}
              required
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <textarea
              placeholder="簡短描述（可選）"
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
              rows={2}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            <button
              type="submit"
              disabled={creating || !formName.trim()}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white rounded-xl py-2 text-sm font-medium transition-colors"
            >
              {creating ? "建立中…" : "建立"}
            </button>
          </form>
        )}

        {loading && (
          <div className="flex justify-center py-20">
            <Spinner />
          </div>
        )}

        {!loading && error && (
          <div className="text-center py-20 text-gray-500">
            <p className="text-5xl mb-4">⚠️</p>
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && etfs.length === 0 && !showForm && (
          <div className="text-center py-20 text-gray-500">
            <p className="text-5xl mb-4">📊</p>
            <p className="text-lg mb-2">還沒有自組 ETF</p>
            <p className="text-sm">點右上角「＋ 新增 ETF」開始組建你的個人投資組合</p>
          </div>
        )}

        {!loading && !error && etfs.length > 0 && (
          <div className="space-y-4">
            {etfs.map((etf) => (
              <ETFCard
                key={etf.id}
                etf={etf}
                favorites={favorites}
                onDelete={() => handleDeleteETF(etf.id)}
                onAddStock={(fav) => handleAddStock(etf.id, fav)}
                onUpdateWeight={(sid, w) => handleUpdateWeight(etf.id, sid, w)}
                onRemoveStock={(sid) => handleRemoveStock(etf.id, sid)}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function ETFCard({ etf, favorites, onDelete, onAddStock, onUpdateWeight, onRemoveStock }) {
  const [showPicker, setShowPicker] = useState(false);
  const stocks = etf.custom_etf_stocks ?? [];
  const addedSymbols = new Set(stocks.map((s) => s.stock_symbol));
  const availableFavorites = favorites.filter((f) => !addedSymbols.has(f.stock_symbol));
  const totalWeight = stocks.reduce((sum, s) => sum + (parseFloat(s.weight) || 0), 0);
  const weightOff = stocks.length > 0 && Math.abs(totalWeight - 100) > 0.5;

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-gray-900 truncate">{etf.etf_name}</h3>
          {etf.description && (
            <p className="text-gray-500 text-sm mt-1 break-words">{etf.description}</p>
          )}
          <p className="text-xs text-gray-400 mt-1">
            {stocks.length} 檔 · 總權重 {totalWeight.toFixed(1)}%
            {weightOff && <span className="text-amber-600 ml-2">⚠ 建議總和為 100%</span>}
          </p>
        </div>
        <button
          onClick={onDelete}
          className="text-gray-400 hover:text-red-500 transition-colors p-1 rounded-lg hover:bg-red-50 shrink-0"
          aria-label={`刪除 ${etf.etf_name}`}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
        </button>
      </div>

      {stocks.length > 0 && (
        <ul className="divide-y divide-gray-100">
          {stocks.map((s) => (
            <li key={s.id} className="px-5 py-3 flex items-center gap-3">
              <span className="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-1 rounded-md shrink-0">
                {s.stock_symbol}
              </span>
              <span className="flex-1 text-sm text-gray-900 truncate">{s.stock_name}</span>
              <WeightInput
                value={s.weight}
                onCommit={(w) => onUpdateWeight(s.id, w)}
              />
              <button
                onClick={() => onRemoveStock(s.id)}
                className="text-gray-400 hover:text-red-500 transition-colors p-1 shrink-0"
                aria-label={`移除 ${s.stock_name}`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="px-5 py-3 bg-gray-50">
        {!showPicker ? (
          <button
            onClick={() => setShowPicker(true)}
            disabled={availableFavorites.length === 0}
            className="w-full text-sm text-blue-600 hover:text-blue-700 disabled:text-gray-400 disabled:cursor-not-allowed font-medium py-1 transition-colors"
          >
            {favorites.length === 0
              ? "先到首頁將股票加入我的最愛"
              : availableFavorites.length === 0
              ? "我的最愛全部已加入此 ETF"
              : "＋ 從我的最愛加入股票"}
          </button>
        ) : (
          <div className="space-y-2">
            <p className="text-xs text-gray-500">從我的最愛選擇：</p>
            <div className="flex flex-wrap gap-2">
              {availableFavorites.map((fav) => (
                <button
                  key={fav.id}
                  onClick={() => {
                    onAddStock(fav);
                    setShowPicker(false);
                  }}
                  className="text-xs border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 px-2.5 py-1 rounded-md transition-colors"
                >
                  {fav.stock_symbol} {fav.stock_name}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowPicker(false)}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              取消
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function WeightInput({ value, onCommit }) {
  const [draft, setDraft] = useState(String(value ?? 0));
  useEffect(() => {
    setDraft(String(value ?? 0));
  }, [value]);
  return (
    <div className="flex items-center gap-1 shrink-0">
      <input
        type="number"
        min="0"
        max="100"
        step="0.1"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          const next = parseFloat(draft);
          const safe = Number.isFinite(next) ? Math.max(0, Math.min(100, next)) : 0;
          if (safe !== (parseFloat(value) || 0)) onCommit(safe);
          setDraft(String(safe));
        }}
        className="w-16 border border-gray-200 rounded-md px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-blue-500 tabular-nums"
      />
      <span className="text-sm text-gray-400">%</span>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="w-8 h-8 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}
