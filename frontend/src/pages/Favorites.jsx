import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { supabase } from "../lib/supabase";

export default function Favorites() {
  const { user, loading: authLoading } = useAuth();
  const [favorites, setFavorites] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deletingSet, setDeletingSet] = useState(new Set());

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    supabase
      .from("favorites")
      .select("*")
      .eq("user_id", user.id)
      .order("added_at", { ascending: false })
      .then(({ data, error: err }) => {
        if (err) {
          setError("收藏清單載入失敗，請重新整理。");
        } else {
          setFavorites(data ?? []);
        }
      })
      .finally(() => setLoading(false));
  }, [user]);

  const handleDelete = async (symbol) => {
    if (deletingSet.has(symbol)) return;
    setDeletingSet((prev) => new Set(prev).add(symbol));
    try {
      await supabase
        .from("favorites")
        .delete()
        .eq("user_id", user.id)
        .eq("stock_symbol", symbol);
      setFavorites((prev) => prev.filter((f) => f.stock_symbol !== symbol));
    } finally {
      setDeletingSet((prev) => {
        const next = new Set(prev);
        next.delete(symbol);
        return next;
      });
    }
  };

  // Not yet determined
  if (authLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  // Not logged in
  if (!user) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-5xl mb-4">🔒</p>
          <h2 className="text-xl font-bold text-gray-800 mb-2">此功能需要登入，敬請期待</h2>
          <p className="text-gray-500 text-sm">登入開放後即可管理你的收藏清單</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-3xl mx-auto px-4 py-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">我的最愛</h2>

        {loading && (
          <div className="flex justify-center py-20">
            <LoadingSpinner />
          </div>
        )}

        {!loading && error && (
          <div className="text-center py-20 text-gray-500">
            <p className="text-5xl mb-4">⚠️</p>
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && favorites.length === 0 && (
          <div className="text-center py-20 text-gray-500">
            <p className="text-5xl mb-4">🌟</p>
            <p className="text-lg mb-2">收藏清單是空的</p>
            <p className="text-sm mb-6">回首頁看看今日選股，把喜歡的加進來吧</p>
            <Link
              to="/"
              className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-xl font-medium transition-colors"
            >
              查看今日選股
            </Link>
          </div>
        )}

        {!loading && !error && favorites.length > 0 && (
          <ul className="space-y-3">
            {favorites.map((fav) => (
              <FavoriteRow
                key={fav.id}
                fav={fav}
                onDelete={handleDelete}
                deleting={deletingSet.has(fav.stock_symbol)}
              />
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}

function FavoriteRow({ fav, onDelete, deleting }) {
  const addedAt = fav.added_at
    ? new Date(fav.added_at).toLocaleDateString("zh-TW", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      })
    : "—";

  return (
    <li className="bg-white rounded-2xl border border-gray-100 px-5 py-4 flex items-center justify-between shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center gap-4">
        <span className="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-1 rounded-md">
          {fav.stock_symbol}
        </span>
        <div>
          <p className="font-semibold text-gray-900 text-sm">{fav.stock_name}</p>
          <p className="text-xs text-gray-400 mt-0.5">加入於 {addedAt}</p>
        </div>
      </div>

      <button
        onClick={() => onDelete(fav.stock_symbol)}
        disabled={deleting}
        className="text-gray-400 hover:text-red-500 transition-colors disabled:opacity-40 p-1 rounded-lg hover:bg-red-50"
        aria-label={`刪除 ${fav.stock_name}`}
      >
        {deleting ? (
          <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        )}
      </button>
    </li>
  );
}

function LoadingSpinner() {
  return (
    <svg className="w-8 h-8 animate-spin text-blue-500" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}
