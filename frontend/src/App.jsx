import { Link, Route, BrowserRouter as Router, Routes, useNavigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import Favorites from "./pages/Favorites";
import Home from "./pages/Home";
import Login from "./pages/Login";

export default function App() {
  return (
    <Router basename={import.meta.env.BASE_URL}>
      <div className="min-h-screen bg-gray-50 flex flex-col">
        <Navbar />
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/favorites" element={<Favorites />} />
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
      <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between gap-4">
        {/* Logo */}
        <Link to="/" className="text-xl font-black text-blue-600 tracking-tight shrink-0">
          oddlot
        </Link>

        {/* Nav links */}
        <nav className="flex items-center gap-1 text-sm font-medium text-gray-600">
          <NavLink to="/">首頁</NavLink>
          <NavLink to="/favorites">我的最愛</NavLink>
        </nav>

        {/* Auth */}
        <div className="shrink-0">
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
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-gray-200 py-6 mt-8">
      <p className="text-center text-sm text-gray-400">
        商務合作請洽{" "}
        <a
          href="mailto:dragondaddy2021@gmail.com"
          className="hover:text-gray-600 transition-colors"
        >
          dragondaddy2021@gmail.com
        </a>
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
