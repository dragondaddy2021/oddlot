import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { supabase } from "../lib/supabase";

export default function Home() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [picks, setPicks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null); // { message, type: "success"|"error"|"info" }
  const [addingSet, setAddingSet] = useState(new Set());

  useEffect(() => {
    // Use Taiwan time (UTC+8) to match the date stored by the daily selection script
    const today = new Date(Date.now() + 8 * 60 * 60 * 1000)
      .toISOString()
      .split("T")[0]; // YYYY-MM-DD in UTC+8
    supabase
      .from("ai_recommendations")
      .select("*")
      .eq("date", today)
      .single()
      .then(({ data, error: err }) => {
        if (err) {
          if (err.code === "PGRST116") {
            // no rows found
            setError("今日選股尚未產生，請稍後再回來查看。");
          } else {
            setError("資料載入失敗，請重新整理頁面。");
          }
        } else {
          setPicks(data?.stocks ?? []);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const showToast = (message, type = "info") => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleAddFavorite = async (stock) => {
    if (!user) {
      navigate("/login");
      return;
    }
    const symbol = stock.symbol;
    if (addingSet.has(symbol)) return;

    setAddingSet((prev) => new Set(prev).add(symbol));
    try {
      const { error: err } = await supabase.from("favorites").insert({
        user_id: user.id,
        stock_symbol: stock.symbol,
        stock_name: stock.name,
      });
      if (err) {
        if (err.code === "23505") {
          showToast(`${stock.name} 已在收藏清單中`, "info");
        } else {
          showToast("加入收藏失敗，請稍後再試", "error");
        }
      } else {
        showToast(`已加入 ${stock.name} 到收藏`, "success");
      }
    } finally {
      setAddingSet((prev) => {
        const next = new Set(prev);
        next.delete(symbol);
        return next;
      });
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Disclaimer banner */}
      <div className="bg-amber-50 border-b border-amber-200">
        <div className="max-w-7xl mx-auto px-4 py-2 text-center text-amber-800 text-xs sm:text-sm">
          ⚠️ 本平台資訊由 AI 產生，僅供參考，不構成投資建議，投資人須自行評估風險
        </div>
      </div>

      {/* Beta notice banner */}
      <div className="bg-blue-50 border-b border-blue-200">
        <div className="max-w-7xl mx-auto px-4 py-2 text-center text-blue-700 text-xs sm:text-sm">
          🚧 本平台目前為測試版，功能持續開發中，歡迎回報問題至{" "}
          <a href="mailto:dragondaddy2021@gmail.com" className="underline hover:text-blue-900">
            dragondaddy2021@gmail.com
          </a>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900">今日 AI 選股</h2>
          <p className="text-gray-500 text-sm mt-1">
            由 Claude AI 從台股上市股票中篩選適合零股長期投資的標的
          </p>
        </div>

        {loading && <SkeletonGrid />}

        {!loading && error && (
          <div className="text-center py-20 text-gray-500">
            <p className="text-5xl mb-4">📭</p>
            <p className="text-lg">{error}</p>
          </div>
        )}

        {!loading && !error && picks.length === 0 && (
          <div className="text-center py-20 text-gray-500">
            <p className="text-5xl mb-4">📭</p>
            <p className="text-lg">今日選股尚未產生，請稍後再回來查看。</p>
          </div>
        )}

        {!loading && !error && picks.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {picks.map((stock) => (
              <StockCard
                key={stock.symbol}
                stock={stock}
                onAddFavorite={handleAddFavorite}
                adding={addingSet.has(stock.symbol)}
                isLoggedIn={!!user}
              />
            ))}
          </div>
        )}
      </main>

      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 px-5 py-3 rounded-xl shadow-lg text-sm font-medium text-white transition-all z-50 ${
            toast.type === "success"
              ? "bg-green-600"
              : toast.type === "error"
              ? "bg-red-600"
              : "bg-gray-700"
          }`}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}

function StockCard({ stock, onAddFavorite, adding, isLoggedIn }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex flex-col gap-3 hover:shadow-md transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-0.5 rounded-md">
            {stock.symbol}
          </span>
          <h3 className="font-bold text-gray-900 mt-1 text-base leading-tight">
            {stock.name}
          </h3>
        </div>
        <span className="text-xl font-bold text-gray-900 tabular-nums">
          ${stock.price?.toFixed(2) ?? "—"}
        </span>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2">
        <Stat label="殖利率" value={stock.yield_rate != null ? `${stock.yield_rate}%` : "—"} color="text-green-600" />
        <Stat label="本益比" value={stock.pe_ratio != null ? `${stock.pe_ratio}x` : "—"} color="text-blue-600" />
      </div>

      {/* AI reason */}
      <p className="text-gray-600 text-sm leading-relaxed flex-1">
        {stock.reason}
      </p>

      {/* Action */}
      <button
        onClick={() => onAddFavorite(stock)}
        disabled={adding}
        className={`w-full mt-auto rounded-xl py-2 text-sm font-medium transition-colors ${
          adding
            ? "bg-gray-100 text-gray-400 cursor-not-allowed"
            : isLoggedIn
            ? "bg-blue-600 hover:bg-blue-700 text-white"
            : "bg-gray-100 hover:bg-gray-200 text-gray-700"
        }`}
      >
        {adding ? "加入中…" : isLoggedIn ? "加入我的最愛" : "登入以加入收藏"}
      </button>
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div className="bg-gray-50 rounded-lg px-3 py-2">
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`font-bold text-sm tabular-nums ${color}`}>{value}</p>
    </div>
  );
}

function SkeletonGrid() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="bg-white rounded-2xl border border-gray-100 p-5 animate-pulse">
          <div className="h-4 w-16 bg-gray-200 rounded mb-2" />
          <div className="h-5 w-24 bg-gray-200 rounded mb-4" />
          <div className="grid grid-cols-2 gap-2 mb-4">
            <div className="h-10 bg-gray-200 rounded-lg" />
            <div className="h-10 bg-gray-200 rounded-lg" />
          </div>
          <div className="space-y-2 mb-4">
            <div className="h-3 bg-gray-200 rounded w-full" />
            <div className="h-3 bg-gray-200 rounded w-5/6" />
            <div className="h-3 bg-gray-200 rounded w-4/6" />
          </div>
          <div className="h-9 bg-gray-200 rounded-xl" />
        </div>
      ))}
    </div>
  );
}
