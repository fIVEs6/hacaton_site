import { FormEvent, ReactNode, useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Alert, errText, Field } from "../ui";

function AuthLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <div className="mb-5 text-center">
          <div className="font-serif text-2xl font-bold">
            Школьные <span className="text-rust">конкурсы</span>
          </div>
          <div className="mx-auto mt-2 h-0.5 w-16 bg-rust" />
        </div>
        <div className="card">
          <h1 className="mb-4 text-xl">{title}</h1>
          {children}
        </div>
      </div>
    </div>
  );
}

export function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [needVerify, setNeedVerify] = useState(false);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={user.role === "admin" ? "/admin" : (loc.state as any)?.from ?? "/"} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);
    try {
      const u = await login(email, password);
      nav(u.role === "admin" ? "/admin" : (loc.state as any)?.from ?? "/", { replace: true });
    } catch (err) {
      setError(errText(err));
      setNeedVerify(err instanceof ApiError && err.status === 403 && /email/i.test(err.message));
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    try {
      const r = await api<{ message: string }>("/auth/resend-verification", { body: { email } });
      setInfo(r.message);
    } catch (err) {
      setError(errText(err));
    }
  }

  return (
    <AuthLayout title="Вход">
      {error && <Alert>{error}</Alert>}
      {info && <Alert kind="ok">{info}</Alert>}
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email">
          <input type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Пароль">
          <input type="password" required autoComplete="current-password" value={password}
                 onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <button className="btn btn-rust w-full" disabled={busy}>Войти</button>
      </form>
      {needVerify && (
        <button className="btn btn-ghost btn-sm mt-3" onClick={resend}>Отправить письмо повторно</button>
      )}
      <div className="mt-4 flex justify-between text-sm">
        <Link to="/forgot-password">Забыли пароль?</Link>
        <Link to="/register">Регистрация</Link>
      </div>
    </AuthLayout>
  );
}

export function Register() {
  const cfg = useQuery({ queryKey: ["config"], queryFn: () => api<{ require_consent: boolean; school_name: string }>("/config") });
  const [f, setF] = useState({
    last_name: "", first_name: "", middle_name: "", grade: "8", class_letter: "", email: "",
    password: "", password2: "", consent: false,
  });
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string | boolean) => setF((p) => ({ ...p, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (f.password !== f.password2) return setError("Пароли не совпадают");
    setBusy(true);
    try {
      const r = await api<{ message: string }>("/auth/register", {
        body: {
          email: f.email, password: f.password, last_name: f.last_name, first_name: f.first_name,
          middle_name: f.middle_name || null, grade: Number(f.grade), class_letter: f.class_letter || null,
          school: cfg.data?.school_name ?? null, consent: f.consent,
        },
      });
      setDone(r.message);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  if (done)
    return (
      <AuthLayout title="Проверьте почту">
        <Alert kind="ok">{done}</Alert>
        <p className="text-sm text-soft">
          В учебном стенде письма попадают в Mailpit: откройте <b>http://localhost:8025</b>.
        </p>
        <Link to="/login" className="btn mt-4 w-full">К входу</Link>
      </AuthLayout>
    );

  return (
    <AuthLayout title="Регистрация ученика">
      {error && <Alert>{error}</Alert>}
      <form onSubmit={submit} className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Фамилия"><input required value={f.last_name} onChange={(e) => set("last_name", e.target.value)} /></Field>
          <Field label="Имя"><input required value={f.first_name} onChange={(e) => set("first_name", e.target.value)} /></Field>
        </div>
        <Field label="Отчество (если есть)"><input value={f.middle_name} onChange={(e) => set("middle_name", e.target.value)} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Класс">
            <select value={f.grade} onChange={(e) => set("grade", e.target.value)}>
              {Array.from({ length: 11 }, (_, i) => i + 1).map((g) => <option key={g}>{g}</option>)}
            </select>
          </Field>
          <Field label="Буква"><input maxLength={2} placeholder="А" value={f.class_letter} onChange={(e) => set("class_letter", e.target.value)} /></Field>
        </div>
        <Field label="Email"><input type="email" required value={f.email} onChange={(e) => set("email", e.target.value)} /></Field>
        <Field label="Пароль" hint="Не короче 8 символов, буквы и цифры">
          <input type="password" required minLength={8} autoComplete="new-password" value={f.password} onChange={(e) => set("password", e.target.value)} />
        </Field>
        <Field label="Повторите пароль">
          <input type="password" required autoComplete="new-password" value={f.password2} onChange={(e) => set("password2", e.target.value)} />
        </Field>
        {cfg.data?.require_consent && (
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" required checked={f.consent} onChange={(e) => set("consent", e.target.checked)} />
            <span>Даю согласие на обработку персональных данных (ФИО, класс, email) для участия в конкурсах.</span>
          </label>
        )}
        <button className="btn btn-rust w-full" disabled={busy}>Зарегистрироваться</button>
      </form>
      <p className="mt-4 text-sm">Уже есть аккаунт? <Link to="/login">Войти</Link></p>
    </AuthLayout>
  );
}

export function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [state, setState] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (!token) return setState({ ok: false, text: "В ссылке нет токена" });
    api<{ message: string }>("/auth/verify-email", { body: { token } })
      .then((r) => setState({ ok: true, text: r.message }))
      .catch((e) => setState({ ok: false, text: errText(e) }));
  }, [token]);

  return (
    <AuthLayout title="Подтверждение email">
      {!state ? <p className="text-soft">Проверяем ссылку…</p> : <Alert kind={state.ok ? "ok" : "error"}>{state.text}</Alert>}
      <Link to="/login" className="btn mt-2 w-full">Перейти ко входу</Link>
    </AuthLayout>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const r = await api<{ message: string }>("/auth/forgot-password", { body: { email } });
      setMsg(r.message);
    } catch (err) {
      setError(errText(err));
    }
  }
  return (
    <AuthLayout title="Восстановление пароля">
      {error && <Alert>{error}</Alert>}
      {msg ? <Alert kind="ok">{msg}</Alert> : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email, указанный при регистрации">
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <button className="btn btn-rust w-full">Отправить ссылку</button>
        </form>
      )}
      <p className="mt-4 text-sm"><Link to="/login">Назад ко входу</Link></p>
    </AuthLayout>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const r = await api<{ message: string }>("/auth/reset-password", { body: { token: params.get("token") ?? "", password } });
      setMsg(r.message);
    } catch (err) {
      setError(errText(err));
    }
  }
  return (
    <AuthLayout title="Новый пароль">
      {error && <Alert>{error}</Alert>}
      {msg ? (
        <>
          <Alert kind="ok">{msg}</Alert>
          <Link to="/login" className="btn w-full">Войти</Link>
        </>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="Новый пароль" hint="Не короче 8 символов, буквы и цифры">
            <input type="password" required minLength={8} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <button className="btn btn-rust w-full">Сохранить пароль</button>
        </form>
      )}
    </AuthLayout>
  );
}
