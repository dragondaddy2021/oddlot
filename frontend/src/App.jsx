import { Link, Route, BrowserRouter as Router, Routes, useNavigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import About from "./pages/About";
import Favorites from "./pages/Favorites";
import Home from "./pages/Home";
import Login from "./pages/Login";
import MyETFs from "./pages/MyETFs";

export default function App() {
  return (
    <Router basename={import.meta.env.BASE_URL}>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Navbar />
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/favorites" element={<Favorites />} />
            <Route path="/my-etfs" element={<MyETFs />} />
            <Route path="/about" element={<About />} />
            <Route path="/login" element={<Login />} />
          </Routes>
        </div>
        <Footer />
      </div>
    </Router>
  );
}

function Navbar() {
  const { user, loading, signOut } = useAuth();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    await signOut();
    navigate("/");
  };

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 py-2 sm:py-0 sm:h-14 flex flex-wrap sm:flex-nowrap items-center justify-between gap-y-2 gap-x-4">
        {/* Logo */}
        <Link to="/" className="order-1 text-xl font-black text-blue-600 tracking-tight shrink-0">
          oddlot
        </Link>

        {/* Auth — mobile: same row as logo; desktop: far right */}
        <div className="order-2 sm:order-3 shrink-0">
          {loading ? (
            <div className="h-8 w-20 bg-gray-100 rounded-lg animate-pulse" />
          ) : user ? (
            <div className="flex items-center gap-3">
              <span className="hidden sm:block text-xs text-gray-500 max-w-[120px] truncate">
                {user.email}
              </span>
              <button
                onClick={handleSignOut}
                className="text-sm text-gray-600 hover:text-red-600 border border-gray-200 hover:border-red-200 px-3 py-1.5 rounded-lg transition-colors"
              >
                登出
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-1.5 rounded-lg transition-colors"
            >
              登入
            </Link>
          )}
        </div>

        {/* Nav links — mobile: wraps to second row, full width, can scroll horizontally if needed */}
        <nav className="order-3 sm:order-2 w-full sm:w-auto flex items-center gap-1 text-sm font-medium text-gray-600 overflow-x-auto -mx-1 px-1">
          <NavLink to="/">首頁</NavLink>
          <NavLink to="/favorites">我的最愛</NavLink>
          <NavLink to="/my-etfs">我的 ETF</NavLink>
          <NavLink to="/about">選股說明</NavLink>
        </nav>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-gray-200 py-6 mt-8 space-y-1">
      <p className="text-center text-sm text-gray-400">
        商務合作請洽{" "}
        <a
          href="mailto:dragondaddy2021@gmail.com"
          className="hover:text-gray-600 transition-colors"
        >
          dragondaddy2021@gmail.com
        </a>
      </p>
      <p className="text-center text-sm text-gray-400">
        © 2026 Dragon. All rights reserved.
      </p>
    </footer>
  );
}

function NavLink({ to, children }) {
  return (
    <Link
      to={to}
      className="px-3 py-1.5 rounded-lg hover:bg-gray-100 hover:text-gray-900 transition-colors"
    >
      {children}
    </Link>
  );
}
