import { ReactNode } from "react";
import { STATUS_LABEL } from "./api";

export function PageTitle({ children, sub }: { children: ReactNode; sub?: ReactNode }) {
  return (
    <div className="mb-5">
      <h1 className="text-2xl sm:text-3xl">{children}</h1>
      {sub && <p className="mt-1 text-soft">{sub}</p>}
    </div>
  );
}

export function Alert({ kind = "error", children }: { kind?: "error" | "ok" | "info"; children: ReactNode }) {
  const cls =
    kind === "error"
      ? "border-rust bg-rust/10 text-rust"
      : kind === "ok"
        ? "border-pine bg-pine/10 text-pine"
        : "border-line bg-sand text-ink";
  return <div className={`mb-4 rounded border px-3 py-2 text-sm ${cls}`}>{children}</div>;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-soft">{hint}</span>}
    </label>
  );
}

const STAMP_COLORS: Record<string, string> = {
  registered: "border-soft text-soft",
  participated: "border-ink text-ink",
  prizewinner: "border-pine text-pine",
  winner: "border-rust text-rust",
  draft: "border-soft text-soft",
  published: "border-pine text-pine",
  finished: "border-ink text-ink",
  upcoming: "border-pine text-pine",
  ongoing: "border-rust text-rust",
};

export function Stamp({ kind, label }: { kind: string; label?: string }) {
  return <span className={`stamp ${STAMP_COLORS[kind] ?? "border-ink text-ink"}`}>{label ?? STATUS_LABEL[kind] ?? kind}</span>;
}

export function Loading() {
  return <p className="py-8 text-center text-soft">Загрузка…</p>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="card text-center text-soft">{children}</div>;
}

export function errText(e: unknown): string {
  return e instanceof Error ? e.message : "Что-то пошло не так";
}
