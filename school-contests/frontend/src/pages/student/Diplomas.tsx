import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, fmtDate } from "../../api";
import { Empty, Loading, PageTitle } from "../../ui";

interface DiplomaItem {
  id: number;
  number: string;
  event_title: string;
  subject: string;
  place: number | null;
  result: string;
  issued_at: string;
}

export default function Diplomas() {
  const q = useQuery({ queryKey: ["my-diplomas"], queryFn: () => api<DiplomaItem[]>("/me/diplomas") });
  if (q.isLoading) return <Loading />;
  return (
    <>
      <PageTitle sub="Дипломы можно открыть в браузере или скачать в PDF.">Мои дипломы</PageTitle>
      {q.data?.length === 0 && (
        <Empty>Дипломов пока нет. Они появятся после того, как школа подведёт итоги. <Link to="/progress">Мой прогресс</Link></Empty>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {q.data?.map((d) => (
          <article key={d.id} className="card border-2 border-double border-ink">
            <p className="text-xs uppercase tracking-widest text-rust">{d.result}{d.place ? ` · ${d.place} место` : ""}</p>
            <h2 className="mt-1 text-lg">{d.event_title}</h2>
            <p className="text-sm text-soft">{d.subject} · выдан {fmtDate(d.issued_at)}</p>
            <p className="mt-2 font-mono text-xs text-soft">{d.number}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              <a className="btn btn-sm" href={`/api/diplomas/${d.id}/pdf?inline=true`} target="_blank" rel="noreferrer">Просмотр</a>
              <a className="btn btn-rust btn-sm" href={`/api/diplomas/${d.id}/pdf`}>Скачать PDF</a>
              <Link className="btn btn-ghost btn-sm" to={`/verify/${d.number}`}>Проверка</Link>
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
