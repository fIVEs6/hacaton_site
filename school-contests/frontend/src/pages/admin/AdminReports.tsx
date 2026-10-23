import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, EventItem } from "../../api";
import { Field, PageTitle } from "../../ui";

const KINDS: [string, string, string][] = [
  ["students", "По ученикам", "Сколько раз участвовал каждый ученик, призовые места, баллы, дипломы."],
  ["classes", "По классам", "Сводка по классам: участие, призёры, победители, баллы."],
  ["events", "По мероприятиям", "Участники, призёры, победители и дипломы по каждому конкурсу."],
  ["period", "За период", "Подробный список участий: кто, где, какой результат и номер диплома."],
];

export default function AdminReports() {
  const [kind, setKind] = useState("students");
  const [grade, setGrade] = useState("");
  const [eventId, setEventId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const events = useQuery({ queryKey: ["admin-events"], queryFn: () => api<EventItem[]>("/admin/events") });

  const link = (format: string) => {
    const p = new URLSearchParams({ format });
    if (grade && kind !== "events") p.set("grade", grade);
    if (eventId && (kind === "period" || kind === "students" || kind === "classes")) p.set("event_id", eventId);
    if (dateFrom) p.set("date_from", dateFrom);
    if (dateTo) p.set("date_to", dateTo);
    return `/api/admin/reports/${kind}?${p}`;
  };

  return (
    <>
      <PageTitle sub="Выгрузка в Excel, CSV или PDF.">Отчёты</PageTitle>
      <div className="mb-5 grid gap-3 sm:grid-cols-2">
        {KINDS.map(([k, title, text]) => (
          <button key={k} onClick={() => setKind(k)}
                  className={`card text-left ${kind === k ? "border-2 border-rust" : "hover:bg-sand"}`}>
            <div className="font-serif text-lg font-bold">{title}</div>
            <div className="text-sm text-soft">{text}</div>
          </button>
        ))}
      </div>

      <section className="card">
        <h2 className="mb-3 text-lg">Фильтры</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {kind !== "events" && (
            <Field label="Параллель">
              <select value={grade} onChange={(e) => setGrade(e.target.value)}>
                <option value="">Все классы</option>
                {Array.from({ length: 11 }, (_, i) => i + 1).map((g) => <option key={g} value={g}>{g} классы</option>)}
              </select>
            </Field>
          )}
          {kind !== "events" && (
            <Field label="Мероприятие">
              <select value={eventId} onChange={(e) => setEventId(e.target.value)}>
                <option value="">Все</option>
                {events.data?.map((e) => <option key={e.id} value={e.id}>{e.title}</option>)}
              </select>
            </Field>
          )}
          <Field label="С даты"><input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} /></Field>
          <Field label="По дату"><input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} /></Field>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <a className="btn btn-rust" href={link("xlsx")}>Скачать XLSX</a>
          <a className="btn" href={link("csv")}>Скачать CSV</a>
          <a className="btn btn-ghost" href={link("pdf")}>Скачать PDF</a>
        </div>
      </section>
    </>
  );
}
