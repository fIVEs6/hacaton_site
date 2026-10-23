import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api";
import { Alert, errText, Loading, PageTitle } from "../../ui";

// Редактор HTML-шаблона диплома. Доступные переменные перечислены в комментарии в начале шаблона.
export default function AdminTemplate() {
  const q = useQuery({ queryKey: ["template"], queryFn: () => api<{ html: string }>("/admin/template") });
  const [html, setHtml] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => { if (q.data) setHtml(q.data.html); }, [q.data]);

  async function save() {
    setMsg("");
    setError("");
    try {
      const r = await api<{ message: string }>("/admin/template", { method: "PUT", body: { html } });
      setMsg(r.message);
    } catch (e) {
      setError(errText(e));
    }
  }

  if (q.isLoading) return <Loading />;
  return (
    <>
      <PageTitle sub="HTML и CSS для генерации PDF. Изменения применяются к новым дипломам.">Шаблон диплома</PageTitle>
      {msg && <Alert kind="ok">{msg}</Alert>}
      {error && <Alert>{error}</Alert>}
      <p className="mb-2 text-sm text-soft">
        Переменные: <code>{"{{ full_name }}"}</code>, <code>{"{{ event_title }}"}</code>, <code>{"{{ subject }}"}</code>,{" "}
        <code>{"{{ level }}"}</code>, <code>{"{{ result_label }}"}</code>, <code>{"{{ place_text }}"}</code>, <code>{"{{ score }}"}</code>,{" "}
        <code>{"{{ date }}"}</code>, <code>{"{{ number }}"}</code>, <code>{"{{ qr }}"}</code>, <code>{"{{ school }}"}</code>, <code>{"{{ team_name }}"}</code>.
      </p>
      <textarea rows={26} className="font-mono text-xs" spellCheck={false} value={html} onChange={(e) => setHtml(e.target.value)} />
      <button className="btn btn-rust mt-3" onClick={save}>Сохранить шаблон</button>
    </>
  );
}
