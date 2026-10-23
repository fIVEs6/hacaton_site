import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, fmtDate } from "../api";
import { Loading } from "../ui";

interface VerifyResult {
  valid: boolean;
  number?: string;
  holder?: string;
  event?: string;
  place?: number | null;
  result?: string;
  issued_at?: string;
}

// Публичная страница проверки диплома (открывается по QR-коду). ФИО показано сокращённо.
export default function Verify() {
  const { number = "" } = useParams();
  const q = useQuery({ queryKey: ["verify", number], queryFn: () => api<VerifyResult>(`/verify/${encodeURIComponent(number)}`) });

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="w-full max-w-md">
        <div className="mb-5 text-center font-serif text-2xl font-bold">
          Школьные <span className="text-rust">конкурсы</span>
        </div>
        <div className="card text-center">
          <h1 className="mb-1 text-xl">Проверка диплома</h1>
          <p className="mb-4 font-mono text-sm text-soft">{number}</p>
          {q.isLoading && <Loading />}
          {q.data && !q.data.valid && (
            <div>
              <span className="stamp border-rust text-rust text-base">Не найден</span>
              <p className="mt-4 text-soft">Диплом с таким номером не выдавался или был отозван.</p>
            </div>
          )}
          {q.data?.valid && (
            <div>
              <span className="stamp border-pine text-pine text-base">Подлинный</span>
              <dl className="mt-5 space-y-3 text-left">
                <div><dt className="label">Награждён(а)</dt><dd className="font-serif text-lg">{q.data.holder}</dd></div>
                <div><dt className="label">Мероприятие</dt><dd>{q.data.event}</dd></div>
                <div>
                  <dt className="label">Результат</dt>
                  <dd>{q.data.result}{q.data.place ? `, ${q.data.place} место` : ""}</dd>
                </div>
                <div><dt className="label">Дата выдачи</dt><dd>{fmtDate(q.data.issued_at ?? "")}</dd></div>
              </dl>
            </div>
          )}
          {q.isError && <p className="text-rust">Не удалось выполнить проверку. Попробуйте позже.</p>}
        </div>
        <p className="mt-4 text-center text-sm"><Link to="/">На главную</Link></p>
      </div>
    </div>
  );
}
