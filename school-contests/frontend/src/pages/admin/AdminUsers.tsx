import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, User } from "../../api";
import { useAuth } from "../../auth";
import { Alert, errText, Empty, Loading, PageTitle } from "../../ui";

export default function AdminUsers() {
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [error, setError] = useState("");

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (role) params.set("role", role);
  const list = useQuery({ queryKey: ["admin-users", q, role], queryFn: () => api<User[]>(`/admin/users?${params}`) });

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<Pick<User, "role" | "is_active">> }) =>
      api<User>(`/admin/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => { setError(""); qc.invalidateQueries({ queryKey: ["admin-users"] }); },
    onError: (e) => setError(errText(e)),
  });

  return (
    <>
      <PageTitle sub="Роли и блокировка учётных записей.">Пользователи</PageTitle>
      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <input className="sm:col-span-2" placeholder="Поиск по ФИО или email" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">Все роли</option>
          <option value="student">Ученики</option>
          <option value="admin">Администраторы</option>
        </select>
      </div>
      {error && <Alert>{error}</Alert>}
      {list.isLoading && <Loading />}
      {list.data?.length === 0 && <Empty>Никого не найдено.</Empty>}
      {!!list.data?.length && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr><th className="th">ФИО</th><th className="th">Класс</th><th className="th">Email</th><th className="th">Роль</th><th className="th">Доступ</th></tr></thead>
            <tbody>
              {list.data.map((u) => (
                <tr key={u.id} className={u.is_active ? "" : "opacity-50"}>
                  <td className="td">{u.full_name}{!u.email_verified && <span className="ml-2 text-xs text-rust">email не подтверждён</span>}</td>
                  <td className="td">{u.class_name}</td>
                  <td className="td">{u.email}</td>
                  <td className="td w-44">
                    <select value={u.role} disabled={u.id === me?.id}
                            onChange={(e) => patch.mutate({ id: u.id, body: { role: e.target.value as User["role"] } })}>
                      <option value="student">Ученик</option>
                      <option value="admin">Администратор</option>
                    </select>
                  </td>
                  <td className="td">
                    <button className="btn btn-ghost btn-sm" disabled={u.id === me?.id}
                            onClick={() => patch.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                      {u.is_active ? "Заблокировать" : "Разблокировать"}
                    </button>
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
