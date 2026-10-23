import { FormEvent, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, EventItem, fmtRange, PHASE_LABEL } from "../../api";
import { Alert, errText, Field, Loading, PageTitle, Stamp } from "../../ui";

export default function EventDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [teamName, setTeamName] = useState("");
  const [code, setCode] = useState("");

  const q = useQuery({ queryKey: ["event", id], queryFn: () => api<EventItem>(`/events/${id}`) });

  function done(message: string) {
    setError("");
    setOk(message);
    qc.invalidateQueries({ queryKey: ["event", id] });
    qc.invalidateQueries({ queryKey: ["events"] });
    qc.invalidateQueries({ queryKey: ["progress"] });
  }
  const run = (fn: () => Promise<{ message?: string }>) =>
    fn().then((r) => done(r?.message ?? "Готово")).catch((e) => { setOk(""); setError(errText(e)); });

  if (q.isLoading) return <Loading />;
  if (q.isError || !q.data) return <Alert>Мероприятие не найдено.</Alert>;
  const e = q.data;
  const team = e.team;

  return (
    <>
      <p className="mb-3 text-sm"><Link to="/">← Все конкурсы</Link></p>
      <PageTitle sub={`${e.subject} · ${e.level_label} · ${fmtRange(e.start_date, e.end_date)}`}>{e.title}</PageTitle>
      <div className="mb-4 flex flex-wrap gap-2">
        <Stamp kind={e.phase} label={PHASE_LABEL[e.phase]} />
        {e.participation_type === "team" && <Stamp kind="participated" label="Командный" />}
        {e.my_status && <Stamp kind={e.my_status} />}
      </div>

      {error && <Alert>{error}</Alert>}
      {ok && <Alert kind="ok">{ok}</Alert>}

      <div className="grid gap-5 md:grid-cols-3">
        <div className="space-y-5 md:col-span-2">
          <section className="card">
            <h2 className="mb-2 text-lg">Описание</h2>
            <p className="whitespace-pre-line">{e.description || "Описание пока не добавлено."}</p>
          </section>
          <section className="card">
            <h2 className="mb-2 text-lg">Правила</h2>
            <p className="whitespace-pre-line">{e.rules || "Правила пока не опубликованы."}</p>
          </section>
        </div>

        <aside className="space-y-5">
          <section className="card">
            <h2 className="mb-3 text-lg">Участие</h2>
            <p className="mb-3 text-sm text-soft">Записалось: {e.participants ?? 0}</p>

            {e.participation_type === "individual" && (
              e.registered ? (
                <>
                  <Alert kind="ok">Вы записаны на мероприятие.</Alert>
                  {e.my_status === "registered" && (
                    <button className="btn btn-ghost btn-sm" onClick={() => run(() => api(`/events/${e.id}/register`, { method: "DELETE" }))}>
                      Отменить запись
                    </button>
                  )}
                </>
              ) : e.can_register ? (
                <button className="btn btn-rust w-full" onClick={() => run(() => api(`/events/${e.id}/register`, { method: "POST" }))}>
                  Записаться
                </button>
              ) : <p className="text-soft">Запись закрыта.</p>
            )}

            {e.participation_type === "team" && team && (
              <>
                <h3 className="text-base">Команда «{team.name}»</h3>
                <p className="mt-2 text-sm text-soft">Код для приглашения друзей:</p>
                <p className="mb-2 select-all rounded border border-dashed border-ink bg-white py-2 text-center font-mono text-xl tracking-widest">
                  {team.join_code}
                </p>
                <ul className="mb-3 space-y-1 text-sm">
                  {team.members.map((m) => (
                    <li key={m.id}>{m.name} <span className="text-soft">({m.class}){m.captain && ", капитан"}</span></li>
                  ))}
                </ul>
                {e.my_status === "registered" && (
                  <button className="btn btn-ghost btn-sm" onClick={() => run(() => api(`/events/${e.id}/register`, { method: "DELETE" }))}>
                    Выйти из команды
                  </button>
                )}
              </>
            )}

            {e.participation_type === "team" && !team && (
              e.can_register ? (
                <div className="space-y-5">
                  <form className="space-y-2" onSubmit={(ev: FormEvent) => { ev.preventDefault(); run(() => api(`/events/${e.id}/teams`, { body: { name: teamName } })); }}>
                    <Field label="Создать команду"><input required minLength={2} placeholder="Название команды" value={teamName} onChange={(x) => setTeamName(x.target.value)} /></Field>
                    <button className="btn btn-rust w-full">Создать</button>
                  </form>
                  <form className="space-y-2 border-t border-line pt-4" onSubmit={(ev: FormEvent) => { ev.preventDefault(); run(() => api(`/events/${e.id}/teams/join`, { body: { code } })); }}>
                    <Field label="Или вступить по коду"><input required placeholder="Например, K7F3QP" value={code} onChange={(x) => setCode(x.target.value)} /></Field>
                    <button className="btn w-full">Вступить</button>
                  </form>
                  {e.team_min_size && <p className="text-xs text-soft">В команде от {e.team_min_size} до {e.team_max_size} человек.</p>}
                </div>
              ) : <p className="text-soft">Запись закрыта.</p>
            )}
          </section>
        </aside>
      </div>
    </>
  );
}
