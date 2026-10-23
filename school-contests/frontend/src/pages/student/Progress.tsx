import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, fmtDate } from "../../api";
import { Empty, Loading, PageTitle, Stamp } from "../../ui";

interface ProgressData {
  stats: {
    total: number; registered: number; participated: number; prizewinner: number; winner: number;
    total_score: number; diplomas: number;
  };
  items: {
    event_id: number; title: string; subject: string; level_label: string; start_date: string; status: string;
    place: number | null; score: number | null; team_name: string | null; diploma_id: number | null;
  }[];
}

export default function Progress() {
  const q = useQuery({ queryKey: ["progress"], queryFn: () => api<ProgressData>("/me/progress") });
  if (q.isLoading) return <Loading />;
  const d = q.data;
  if (!d) return null;

  const tiles: [string, number | string][] = [
    ["Всего участий", d.stats.total],
    ["Победы", d.stats.winner],
    ["Призовые места", d.stats.prizewinner],
    ["Сумма баллов", d.stats.total_score],
    ["Дипломы", d.stats.diplomas],
  ];

  return (
    <>
      <PageTitle sub="Ваши мероприятия, результаты и баллы.">Мой прогресс</PageTitle>
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        {tiles.map(([label, value]) => (
          <div key={label} className="card text-center">
            <div className="font-serif text-3xl font-bold text-rust">{value}</div>
            <div className="mt-1 text-xs uppercase tracking-wider text-soft">{label}</div>
          </div>
        ))}
      </div>

      {d.items.length === 0 ? (
        <Empty>Вы пока ни на что не записаны. <Link to="/">Посмотреть конкурсы</Link></Empty>
      ) : (
        <div className="space-y-3">
          {d.items.map((i) => (
            <div key={i.event_id} className="card flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <Link to={`/events/${i.event_id}`} className="font-serif text-lg font-bold text-ink">{i.title}</Link>
                <p className="text-sm text-soft">
                  {i.subject} · {i.level_label} · {fmtDate(i.start_date)}
                  {i.team_name && ` · команда «${i.team_name}»`}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-right text-sm">
                  {i.place && <div>Место: <b>{i.place}</b></div>}
                  {i.score !== null && <div>Баллы: <b>{i.score}</b></div>}
                </div>
                <Stamp kind={i.status} />
                {i.diploma_id && (
                  <a className="btn btn-ghost btn-sm" href={`/api/diplomas/${i.diploma_id}/pdf`}>Диплом</a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
