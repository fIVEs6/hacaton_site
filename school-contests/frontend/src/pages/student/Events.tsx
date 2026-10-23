import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, EventItem, fmtRange, PHASE_LABEL } from "../../api";
import { Alert, Empty, errText, Loading, PageTitle, Stamp } from "../../ui";

interface Feed {
  items: EventItem[];
  subjects: string[];
}

export default function Events() {
  const qc = useQueryClient();
  const [filters, setFilters] = useState({ q: "", subject: "", status: "", date_from: "", date_to: "" });
  const [error, setError] = useState("");
  const set = (k: string, v: string) => setFilters((p) => ({ ...p, [k]: v }));

  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => v && params.set(k, v));
  const feed = useQuery({ queryKey: ["events", filters], queryFn: () => api<Feed>(`/events?${params}`) });

  const register = useMutation({
    mutationFn: (id: number) => api(`/events/${id}/register`, { method: "POST" }),
    onSuccess: () => {
      setError("");
      qc.invalidateQueries({ queryKey: ["events"] });
      qc.invalidateQueries({ queryKey: ["progress"] });
    },
    onError: (e) => setError(errText(e)),
  });

  return (
    <>
      <PageTitle sub="Анонсы школьных мероприятий. Запишитесь, и результаты появятся в разделе «Мой прогресс».">
        Конкурсы и олимпиады
      </PageTitle>

      <div className="card mb-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <input placeholder="Поиск по названию" value={filters.q} onChange={(e) => set("q", e.target.value)} />
        <select value={filters.subject} onChange={(e) => set("subject", e.target.value)}>
          <option value="">Все предметы</option>
          {feed.data?.subjects.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.status} onChange={(e) => set("status", e.target.value)}>
          <option value="">Любой статус</option>
          <option value="upcoming">Скоро</option>
          <option value="ongoing">Идут сейчас</option>
          <option value="finished">Завершены</option>
        </select>
        <input type="date" aria-label="С даты" value={filters.date_from} onChange={(e) => set("date_from", e.target.value)} />
        <input type="date" aria-label="По дату" value={filters.date_to} onChange={(e) => set("date_to", e.target.value)} />
      </div>

      {error && <Alert>{error}</Alert>}
      {feed.isLoading && <Loading />}
      {feed.data?.items.length === 0 && <Empty>По заданным условиям мероприятий нет.</Empty>}

      <div className="space-y-4">
        {feed.data?.items.map((e) => (
          <article key={e.id} className="card">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <h2 className="text-xl">
                  <Link to={`/events/${e.id}`} className="text-ink">{e.title}</Link>
                </h2>
                <p className="mt-1 text-sm text-soft">
                  {e.subject} · {e.level_label} · {fmtRange(e.start_date, e.end_date)}
                  {e.participation_type === "team" && " · командный"}
                </p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <Stamp kind={e.phase} label={PHASE_LABEL[e.phase]} />
                {e.registered && e.my_status && <Stamp kind={e.my_status} />}
              </div>
            </div>
            <p className="mt-3 line-clamp-2 text-ink/80">{e.description}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link to={`/events/${e.id}`} className="btn btn-ghost btn-sm">Подробнее</Link>
              {e.can_register && !e.registered && e.participation_type === "individual" && (
                <button className="btn btn-rust btn-sm" disabled={register.isPending} onClick={() => register.mutate(e.id)}>
                  Записаться
                </button>
              )}
              {e.can_register && !e.registered && e.participation_type === "team" && (
                <Link to={`/events/${e.id}`} className="btn btn-rust btn-sm">Создать или найти команду</Link>
              )}
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
