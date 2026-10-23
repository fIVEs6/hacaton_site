import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, EVENT_STATUS_LABEL, EventItem, fmtRange, STATUS_LABEL } from "../../api";
import { Alert, Empty, errText, Loading, PageTitle, Stamp } from "../../ui";
import EventForm from "./EventForm";

// ---------- Типы ответов API ----------
interface Res { place: number | null; score: number | null; status: string }
interface Dip { id: number; number: string; revoked: boolean }
interface Participants {
  type: "individual" | "team";
  individual: { registration_id: number; name: string; class: string; email: string; status: string; source: string; result: Res | null; diploma: Dip | null }[];
  teams: { team_id: number; name: string; result: Res | null; members: { name: string; class: string; diploma: Dip | null }[] }[];
}
interface PreviewRow {
  row: number; status: "ok" | "new" | "ambiguous" | "error"; name: string; class: string; email: string; team: string;
  message: string; candidates?: { id: number; name: string; class: string; email: string }[];
}
interface Preview { id: number; total: number; ok: number; new: number; ambiguous: number; errors: number; rows: PreviewRow[] }
interface EventDiploma { id: number; number: string; holder: string; class: string; result: string; issued_at: string; revoked: boolean }

type Tab = "participants" | "results" | "diplomas" | "settings";
const TABS: [Tab, string][] = [
  ["participants", "Участники и импорт"],
  ["results", "Результаты"],
  ["diplomas", "Дипломы"],
  ["settings", "Настройки"],
];

export default function AdminEvent() {
  const { id } = useParams();
  const [tab, setTab] = useState<Tab>("participants");
  const q = useQuery({ queryKey: ["admin-event", id], queryFn: () => api<EventItem>(`/admin/events/${id}`) });
  if (q.isLoading) return <Loading />;
  if (!q.data) return <Alert>Мероприятие не найдено.</Alert>;
  const e = q.data;

  return (
    <>
      <p className="mb-3 text-sm"><Link to="/admin">← Все мероприятия</Link></p>
      <PageTitle sub={`${e.subject} · ${e.level_label} · ${fmtRange(e.start_date, e.end_date)} · ${e.participation_type === "team" ? "командный" : "индивидуальный"}`}>
        {e.title}
      </PageTitle>
      <div className="mb-5"><Stamp kind={e.status} label={EVENT_STATUS_LABEL[e.status]} /></div>

      <div className="mb-5 flex flex-wrap gap-1 border-b-2 border-ink">
        {TABS.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
                  className={`px-4 py-2 font-bold ${tab === key ? "bg-ink text-paper" : "text-soft hover:bg-sand"}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "participants" && <ParticipantsTab event={e} />}
      {tab === "results" && <ResultsTab event={e} />}
      {tab === "diplomas" && <DiplomasTab event={e} />}
      {tab === "settings" && <SettingsTab event={e} />}
    </>
  );
}

// ---------- Участники и импорт ----------

function ParticipantsTab({ event }: { event: EventItem }) {
  const qc = useQueryClient();
  const [preview, setPreview] = useState<Preview | null>(null);
  const [choices, setChoices] = useState<Record<string, number>>({});
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [fileKey, setFileKey] = useState(0);

  const list = useQuery({ queryKey: ["participants", event.id], queryFn: () => api<Participants>(`/admin/events/${event.id}/participants`) });

  async function upload(file: File | undefined) {
    if (!file) return;
    setError("");
    setMsg("");
    setChoices({});
    const form = new FormData();
    form.append("file", file);
    try {
      setPreview(await api<Preview>(`/admin/events/${event.id}/imports`, { form }));
    } catch (err) {
      setPreview(null);
      setError(errText(err));
    }
  }

  const commit = useMutation({
    mutationFn: () => api<{ registered: number; created_users: number; skipped_existing: number; errors: unknown[] }>(
      `/admin/imports/${preview!.id}/commit`, { body: { choices } }),
    onSuccess: (r) => {
      setMsg(`Записано: ${r.registered} (новых учётных записей: ${r.created_users}), уже были в списке: ${r.skipped_existing}, пропущено из-за ошибок: ${r.errors.length}.`);
      setPreview(null);
      setFileKey((k) => k + 1);
      qc.invalidateQueries({ queryKey: ["participants", event.id] });
      qc.invalidateQueries({ queryKey: ["admin-event", String(event.id)] });
    },
    onError: (e) => setError(errText(e)),
  });

  const color = (s: string) => (s === "ok" ? "text-pine" : s === "new" ? "text-ink" : s === "ambiguous" ? "text-rust" : "text-rust");
  const label: Record<string, string> = { ok: "Найден", new: "Новый", ambiguous: "Выберите", error: "Ошибка" };

  return (
    <div className="space-y-6">
      {msg && <Alert kind="ok">{msg}</Alert>}
      {error && <Alert>{error}</Alert>}

      <section className="card">
        <h2 className="mb-2 text-lg">Загрузка списка участников</h2>
        <p className="mb-3 text-sm text-soft">
          Файл CSV или XLSX с колонками: <b>ФИО</b> (или Фамилия и Имя), <b>Класс</b> (например 8Б), необязательно <b>Email</b>
          {event.participation_type === "team" && <> и <b>Команда</b></>}. Сначала будет предпросмотр, записи создаются только после подтверждения.
        </p>
        <input key={fileKey} type="file" accept=".csv,.xlsx" onChange={(e) => upload(e.target.files?.[0])} />

        {preview && (
          <div className="mt-4">
            <p className="mb-2 text-sm">
              Строк: <b>{preview.total}</b> · найдено: <b className="text-pine">{preview.ok}</b> · новых: <b>{preview.new}</b> ·
              неоднозначных: <b className="text-rust">{preview.ambiguous}</b> · с ошибками: <b className="text-rust">{preview.errors}</b>
            </p>
            <div className="max-h-96 overflow-auto border border-line">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-card"><tr>
                  <th className="th">№</th><th className="th">Ученик</th><th className="th">Класс</th><th className="th">Статус</th><th className="th">Комментарий</th>
                </tr></thead>
                <tbody>
                  {preview.rows.map((r) => (
                    <tr key={r.row}>
                      <td className="td">{r.row}</td>
                      <td className="td">{r.name}{r.team && <span className="text-soft"> · {r.team}</span>}</td>
                      <td className="td">{r.class}</td>
                      <td className={`td font-bold ${color(r.status)}`}>{label[r.status]}</td>
                      <td className="td">
                        {r.status === "ambiguous" ? (
                          <select value={choices[String(r.row)] ?? ""} onChange={(e) => setChoices((c) => ({ ...c, [String(r.row)]: Number(e.target.value) }))}>
                            <option value="">— выберите ученика —</option>
                            {r.candidates?.map((c) => <option key={c.id} value={c.id}>{c.name}, {c.class} ({c.email})</option>)}
                          </select>
                        ) : r.message}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex gap-2">
              <button className="btn btn-rust" disabled={commit.isPending || preview.ok + preview.new + preview.ambiguous === 0} onClick={() => commit.mutate()}>
                Применить импорт
              </button>
              <button className="btn btn-ghost" onClick={() => { setPreview(null); setFileKey((k) => k + 1); }}>Отмена</button>
            </div>
            {preview.errors > 0 && <p className="mt-2 text-xs text-soft">Строки с ошибками будут пропущены. Исправьте файл и загрузите его снова, если их нужно добавить.</p>}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-lg">Записавшиеся</h2>
        {list.isLoading && <Loading />}
        {list.data?.type === "individual" && (
          list.data.individual.length === 0 ? <Empty>Пока никто не записался.</Empty> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr><th className="th">Ученик</th><th className="th">Класс</th><th className="th">Email</th><th className="th">Статус</th><th className="th">Запись</th></tr></thead>
                <tbody>
                  {list.data.individual.map((p) => (
                    <tr key={p.registration_id}>
                      <td className="td">{p.name}</td><td className="td">{p.class}</td><td className="td">{p.email}</td>
                      <td className="td"><Stamp kind={p.status} /></td>
                      <td className="td text-soft">{p.source === "import" ? "импорт" : "сам(а)"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
        {list.data?.type === "team" && (
          list.data.teams.length === 0 ? <Empty>Команд пока нет.</Empty> : (
            <div className="grid gap-3 sm:grid-cols-2">
              {list.data.teams.map((t) => (
                <div key={t.team_id} className="card">
                  <div className="flex items-center justify-between"><h3 className="text-base">{t.name}</h3>{t.result && <Stamp kind={t.result.status} />}</div>
                  <ul className="mt-2 text-sm">{t.members.map((m, i) => <li key={i}>{m.name} <span className="text-soft">({m.class})</span></li>)}</ul>
                </div>
              ))}
            </div>
          )
        )}
      </section>
    </div>
  );
}

// ---------- Результаты ----------

interface RowState { place: string; score: string; status: string }

function ResultsTab({ event }: { event: EventItem }) {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["participants", event.id], queryFn: () => api<Participants>(`/admin/events/${event.id}/participants`) });
  const [rows, setRows] = useState<Record<string, RowState>>({});
  const [dirty, setDirty] = useState<Set<string>>(new Set());
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  // Заполняем таблицу из загруженных данных
  useEffect(() => {
    if (!list.data) return;
    const init: Record<string, RowState> = {};
    const fill = (key: string, r: Res | null, status: string) => {
      init[key] = { place: r?.place ? String(r.place) : "", score: r?.score != null ? String(r.score) : "", status: r ? r.status : status === "registered" ? "" : status };
    };
    list.data.individual.forEach((p) => fill(`r:${p.registration_id}`, p.result, p.status));
    list.data.teams.forEach((t) => fill(`t:${t.team_id}`, t.result, ""));
    setRows(init);
    setDirty(new Set());
  }, [list.data]);

  function change(key: string, field: keyof RowState, value: string) {
    setRows((prev) => {
      const next = { ...prev[key], [field]: value };
      // Подсказка: 1 место → победитель, 2–3 → призёр
      if (field === "place" && (next.status === "" || next.status === "participated")) {
        if (value === "1") next.status = "winner";
        else if (value === "2" || value === "3") next.status = "prizewinner";
        else if (value && next.status === "") next.status = "participated";
      }
      return { ...prev, [key]: next };
    });
    setDirty((d) => new Set(d).add(key));
  }

  const save = useMutation({
    mutationFn: () => {
      const items = [...dirty].filter((k) => rows[k]?.status).map((k) => {
        const r = rows[k];
        const base = { place: r.place ? Number(r.place) : null, score: r.score !== "" ? Number(r.score) : null, status: r.status };
        return k.startsWith("r:") ? { ...base, registration_id: Number(k.slice(2)) } : { ...base, team_id: Number(k.slice(2)) };
      });
      if (items.length === 0) throw new Error("Нет изменений для сохранения: выберите статус участия.");
      return api<{ saved: number }>(`/admin/events/${event.id}/results`, { method: "PUT", body: { items } });
    },
    onSuccess: (r) => {
      setError("");
      setMsg(`Результатов сохранено: ${r.saved}`);
      qc.invalidateQueries({ queryKey: ["participants", event.id] });
    },
    onError: (e) => { setMsg(""); setError(errText(e)); },
  });

  if (list.isLoading) return <Loading />;
  const d = list.data;
  if (!d || (d.individual.length === 0 && d.teams.length === 0)) return <Empty>Сначала нужны участники: загрузите список или дождитесь записи учеников.</Empty>;

  const cells = (key: string) => (
    <>
      <td className="td w-24"><input type="number" min={1} value={rows[key]?.place ?? ""} onChange={(e) => change(key, "place", e.target.value)} /></td>
      <td className="td w-28"><input type="number" min={0} step="0.5" value={rows[key]?.score ?? ""} onChange={(e) => change(key, "score", e.target.value)} /></td>
      <td className="td w-44">
        <select value={rows[key]?.status ?? ""} onChange={(e) => change(key, "status", e.target.value)}>
          <option value="">— не внесён —</option>
          {["participated", "prizewinner", "winner"].map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
        </select>
      </td>
    </>
  );

  return (
    <>
      {msg && <Alert kind="ok">{msg}</Alert>}
      {error && <Alert>{error}</Alert>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr><th className="th">{d.type === "team" ? "Команда" : "Ученик"}</th><th className="th">Место</th><th className="th">Баллы</th><th className="th">Статус</th></tr></thead>
          <tbody>
            {d.individual.map((p) => (
              <tr key={p.registration_id}><td className="td">{p.name} <span className="text-soft">({p.class})</span></td>{cells(`r:${p.registration_id}`)}</tr>
            ))}
            {d.teams.map((t) => (
              <tr key={t.team_id}>
                <td className="td">{t.name}<div className="text-xs text-soft">{t.members.map((m) => m.name).join(", ")}</div></td>
                {cells(`t:${t.team_id}`)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-4 flex items-center gap-3">
        <button className="btn btn-rust" disabled={save.isPending || dirty.size === 0} onClick={() => save.mutate()}>Сохранить результаты</button>
        {dirty.size > 0 && <span className="text-sm text-soft">Изменено строк: {dirty.size}</span>}
      </div>
      <p className="mt-3 text-xs text-soft">Для команды результат сохраняется за всю команду и применяется ко всем её участникам. Дальше откройте вкладку «Дипломы».</p>
    </>
  );
}

// ---------- Дипломы ----------

function DiplomasTab({ event }: { event: EventItem }) {
  const qc = useQueryClient();
  const [withParticipants, setWithParticipants] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const list = useQuery({ queryKey: ["event-diplomas", event.id], queryFn: () => api<EventDiploma[]>(`/admin/events/${event.id}/diplomas`) });

  const gen = useMutation({
    mutationFn: () => api<{ issued: number; skipped: number }>(`/admin/events/${event.id}/diplomas`, { body: { include_participants: withParticipants } }),
    onSuccess: (r) => {
      setError("");
      setMsg(`Выдано дипломов: ${r.issued}. Уже были выданы ранее: ${r.skipped}.`);
      qc.invalidateQueries({ queryKey: ["event-diplomas", event.id] });
      qc.invalidateQueries({ queryKey: ["participants", event.id] });
    },
    onError: (e) => { setMsg(""); setError(errText(e)); },
  });

  const revoke = useMutation({
    mutationFn: (id: number) => api<{ message: string }>(`/admin/diplomas/${id}/revoke`, { method: "POST" }),
    onSuccess: (r) => { setError(""); setMsg(r.message); qc.invalidateQueries({ queryKey: ["event-diplomas", event.id] }); },
    onError: (e) => setError(errText(e)),
  });

  return (
    <>
      {msg && <Alert kind="ok">{msg}</Alert>}
      {error && <Alert>{error}</Alert>}
      <section className="card mb-5">
        <h2 className="mb-2 text-lg">Массовая генерация</h2>
        <p className="mb-3 text-sm text-soft">Диплом получают призёры и победители. Для команды диплом создаётся каждому участнику. Уже выданные дипломы не дублируются.</p>
        <label className="mb-3 flex items-center gap-2 text-sm">
          <input type="checkbox" checked={withParticipants} onChange={(e) => setWithParticipants(e.target.checked)} />
          Также выдать сертификаты участникам (без призового места)
        </label>
        <button className="btn btn-rust" disabled={gen.isPending} onClick={() => gen.mutate()}>
          {gen.isPending ? "Генерация…" : "Сгенерировать дипломы"}
        </button>
      </section>

      {list.isLoading && <Loading />}
      {list.data?.length === 0 && <Empty>Дипломов по этому мероприятию пока нет.</Empty>}
      {!!list.data?.length && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr><th className="th">Номер</th><th className="th">Ученик</th><th className="th">Класс</th><th className="th">Результат</th><th className="th" /></tr></thead>
            <tbody>
              {list.data.map((d) => (
                <tr key={d.id} className={d.revoked ? "opacity-50" : ""}>
                  <td className="td font-mono text-xs">{d.number}</td>
                  <td className="td">{d.holder}</td><td className="td">{d.class}</td><td className="td">{d.result}</td>
                  <td className="td whitespace-nowrap text-right">
                    {d.revoked ? <span className="text-rust">отозван</span> : (
                      <>
                        <a className="btn btn-ghost btn-sm" href={`/api/diplomas/${d.id}/pdf?inline=true`} target="_blank" rel="noreferrer">PDF</a>{" "}
                        <button className="btn btn-ghost btn-sm" onClick={() => confirm("Отозвать диплом? Проверка по QR перестанет его подтверждать.") && revoke.mutate(d.id)}>Отозвать</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

// ---------- Настройки ----------

function SettingsTab({ event }: { event: EventItem }) {
  const qc = useQueryClient();
  const nav = useNavigate();
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  async function remove() {
    if (!confirm("Удалить мероприятие вместе с записями и результатами?")) return;
    try {
      await api(`/admin/events/${event.id}`, { method: "DELETE" });
      qc.invalidateQueries({ queryKey: ["admin-events"] });
      nav("/admin");
    } catch (e) {
      setError(errText(e));
    }
  }

  return (
    <div className="space-y-5">
      {msg && <Alert kind="ok">{msg}</Alert>}
      {error && <Alert>{error}</Alert>}
      <EventForm initial={event} onSaved={() => {
        setMsg("Изменения сохранены");
        qc.invalidateQueries({ queryKey: ["admin-event", String(event.id)] });
        qc.invalidateQueries({ queryKey: ["admin-events"] });
      }} />
      <div className="card border-rust">
        <h2 className="mb-2 text-lg text-rust">Удаление</h2>
        <p className="mb-3 text-sm text-soft">Мероприятие, по которому выданы дипломы, удалить нельзя — переведите его в статус «Завершено».</p>
        <button className="btn btn-ghost" onClick={remove}>Удалить мероприятие</button>
      </div>
    </div>
  );
}
