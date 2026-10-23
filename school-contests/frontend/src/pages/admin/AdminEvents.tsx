import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, EVENT_STATUS_LABEL, EventItem, fmtRange } from "../../api";
import { Empty, Loading, PageTitle, Stamp } from "../../ui";
import EventForm from "./EventForm";

export default function AdminEvents() {
  const nav = useNavigate();
  const [creating, setCreating] = useState(false);
  const q = useQuery({ queryKey: ["admin-events"], queryFn: () => api<EventItem[]>("/admin/events") });

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle sub="Создавайте конкурсы, загружайте участников, вносите результаты и выдавайте дипломы.">Мероприятия</PageTitle>
        <button className="btn btn-rust" onClick={() => setCreating(!creating)}>{creating ? "Отмена" : "+ Новое мероприятие"}</button>
      </div>

      {creating && (
        <div className="mb-6">
          <EventForm onSaved={(e) => nav(`/admin/events/${e.id}`)} />
        </div>
      )}

      {q.isLoading && <Loading />}
      {q.data?.length === 0 && <Empty>Мероприятий пока нет.</Empty>}
      <div className="space-y-3">
        {q.data?.map((e) => (
          <div key={e.id} className="card flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <Link to={`/admin/events/${e.id}`} className="font-serif text-lg font-bold text-ink">{e.title}</Link>
              <p className="text-sm text-soft">
                {e.subject} · {e.level_label} · {fmtRange(e.start_date, e.end_date)} ·{" "}
                {e.participation_type === "team" ? "командный" : "индивидуальный"} · записано: {e.participants ?? 0}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Stamp kind={e.status} label={EVENT_STATUS_LABEL[e.status]} />
              <Link to={`/admin/events/${e.id}`} className="btn btn-ghost btn-sm">Открыть</Link>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
