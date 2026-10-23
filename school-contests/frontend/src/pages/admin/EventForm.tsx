import { FormEvent, useState } from "react";
import { api, EVENT_STATUS_LABEL, EventItem, LEVELS } from "../../api";
import { Alert, errText, Field } from "../../ui";

// Форма создания и редактирования мероприятия (используется в списке и в карточке мероприятия)
export default function EventForm({
  initial,
  onSaved,
}: {
  initial?: EventItem;
  onSaved: (e: EventItem) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [f, setF] = useState({
    title: initial?.title ?? "",
    subject: initial?.subject ?? "",
    level: initial?.level ?? "school",
    participation_type: initial?.participation_type ?? "individual",
    team_min_size: String(initial?.team_min_size ?? 2),
    team_max_size: String(initial?.team_max_size ?? 5),
    start_date: initial?.start_date ?? today,
    end_date: initial?.end_date ?? today,
    status: initial?.status ?? "draft",
    description: initial?.description ?? "",
    rules: initial?.rules ?? "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));
  const team = f.participation_type === "team";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const body = {
      ...f,
      team_min_size: team ? Number(f.team_min_size) : null,
      team_max_size: team ? Number(f.team_max_size) : null,
    };
    try {
      const saved = initial
        ? await api<EventItem>(`/admin/events/${initial.id}`, { method: "PUT", body })
        : await api<EventItem>("/admin/events", { body });
      onSaved(saved);
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="card space-y-3">
      {error && <Alert>{error}</Alert>}
      <Field label="Название"><input required minLength={3} value={f.title} onChange={(e) => set("title", e.target.value)} /></Field>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Предмет"><input required value={f.subject} onChange={(e) => set("subject", e.target.value)} placeholder="Математика" /></Field>
        <Field label="Уровень">
          <select value={f.level} onChange={(e) => set("level", e.target.value)}>
            {LEVELS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <Field label="Формат">
          <select value={f.participation_type} onChange={(e) => set("participation_type", e.target.value)} disabled={!!initial && (initial.participants ?? 0) > 0}>
            <option value="individual">Индивидуальный</option>
            <option value="team">Командный</option>
          </select>
        </Field>
      </div>
      {team && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Минимум в команде"><input type="number" min={2} max={50} value={f.team_min_size} onChange={(e) => set("team_min_size", e.target.value)} /></Field>
          <Field label="Максимум в команде"><input type="number" min={2} max={50} value={f.team_max_size} onChange={(e) => set("team_max_size", e.target.value)} /></Field>
        </div>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field label="Дата начала"><input type="date" required value={f.start_date} onChange={(e) => set("start_date", e.target.value)} /></Field>
        <Field label="Дата окончания"><input type="date" required min={f.start_date} value={f.end_date} onChange={(e) => set("end_date", e.target.value)} /></Field>
        <Field label="Статус">
          <select value={f.status} onChange={(e) => set("status", e.target.value)}>
            {Object.entries(EVENT_STATUS_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Описание"><textarea rows={4} value={f.description} onChange={(e) => set("description", e.target.value)} /></Field>
      <Field label="Правила"><textarea rows={4} value={f.rules} onChange={(e) => set("rules", e.target.value)} /></Field>
      <p className="text-xs text-soft">Ученики видят только мероприятия со статусом «Опубликовано» и «Завершено».</p>
      <button className="btn btn-rust" disabled={busy}>{initial ? "Сохранить изменения" : "Создать мероприятие"}</button>
    </form>
  );
}
