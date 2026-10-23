import { ReactNode, useState } from "react";
import { Link, NavLink, Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import { Loading } from "./ui";
import { Login, Register, VerifyEmail, ForgotPassword, ResetPassword } from "./pages/Auth";
import Verify from "./pages/Verify";
import Events from "./pages/student/Events";
import EventDetail from "./pages/student/EventDetail";
import Progress from "./pages/student/Progress";
import Diplomas from "./pages/student/Diplomas";
import Profile from "./pages/student/Profile";
import AdminEvents from "./pages/admin/AdminEvents";
import AdminEvent from "./pages/admin/AdminEvent";
import AdminReports from "./pages/admin/AdminReports";
import AdminUsers from "./pages/admin/AdminUsers";
import AdminTemplate from "./pages/admin/AdminTemplate";

const studentNav: [string, string][] = [
  ["/", "Конкурсы"],
  ["/progress", "Мой прогресс"],
  ["/diplomas", "Мои дипломы"],
  ["/profile", "Профиль"],
];
const adminNav: [string, string][] = [
  ["/admin", "Мероприятия"],
  ["/admin/reports", "Отчёты"],
  ["/admin/users", "Пользователи"],
  ["/admin/template", "Шаблон диплома"],
];

function Shell() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const nav = user?.role === "admin" ? adminNav : studentNav;
  const linkCls = ({ isActive }: { isActive: boolean }) =>
    `block border-b-2 px-1 py-2 font-bold no-underline hover:no-underline ${
      isActive ? "border-rust text-ink" : "border-transparent text-soft hover:text-ink"
    }`;
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b-2 border-ink bg-card">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="font-serif text-xl font-bold text-ink no-underline hover:no-underline">
            Школьные <span className="text-rust">конкурсы</span>
          </Link>
          <button className="btn btn-ghost btn-sm md:hidden" onClick={() => setOpen(!open)} aria-label="Меню">
            {open ? "Закрыть" : "Меню"}
          </button>
          <nav className="hidden items-center gap-5 md:flex">
            {nav.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/" || to === "/admin"} className={linkCls}>
                {label}
              </NavLink>
            ))}
            <span className="text-sm text-soft">{user?.last_name} {user?.first_name?.[0]}.</span>
            <button className="btn btn-ghost btn-sm" onClick={() => logout()}>
              Выйти
            </button>
          </nav>
        </div>
        {open && (
          <nav className="border-t border-line px-4 pb-3 md:hidden" onClick={() => setOpen(false)}>
            {nav.map(([to, label]) => (
              <NavLink key={to} to={to} end={to === "/" || to === "/admin"} className={linkCls}>
                {label}
              </NavLink>
            ))}
            <button className="btn btn-ghost btn-sm mt-2" onClick={() => logout()}>
              Выйти ({user?.last_name})
            </button>
          </nav>
        )}
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-6">
        <Outlet />
      </main>
      <footer className="border-t border-line py-4 text-center text-xs text-soft">
        Школьная платформа конкурсов · прототип
      </footer>
    </div>
  );
}

function Protected({ role, children }: { role?: "admin"; children: ReactNode }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  if (role === "admin" && user.role !== "admin") return <Navigate to="/" replace />;
  return <>{children}</>;
}

function Home() {
  const { user } = useAuth();
  return user?.role === "admin" ? <Navigate to="/admin" replace /> : <Events />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify/:number" element={<Verify />} />
      <Route
        element={
          <Protected>
            <Shell />
          </Protected>
        }
      >
        <Route path="/" element={<Home />} />
        <Route path="/events/:id" element={<EventDetail />} />
        <Route path="/progress" element={<Progress />} />
        <Route path="/diplomas" element={<Diplomas />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/admin" element={<Protected role="admin"><AdminEvents /></Protected>} />
        <Route path="/admin/events/:id" element={<Protected role="admin"><AdminEvent /></Protected>} />
        <Route path="/admin/reports" element={<Protected role="admin"><AdminReports /></Protected>} />
        <Route path="/admin/users" element={<Protected role="admin"><AdminUsers /></Protected>} />
        <Route path="/admin/template" element={<Protected role="admin"><AdminTemplate /></Protected>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
