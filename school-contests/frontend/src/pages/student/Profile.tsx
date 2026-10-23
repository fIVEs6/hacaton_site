import { FormEvent, useState } from "react";
import { useAuth } from "../../auth";
import { api, User } from "../../api";
import { Alert, errText, Field, PageTitle } from "../../ui";

export default function Profile() {
  const { user, refresh } = useAuth();
  const [f, setF] = useState({
    last_name: user?.last_name ?? "", first_name: user?.first_name ?? "", middle_name: user?.middle_name ?? "",
    grade: String(user?.grade ?? 8), class_letter: user?.class_letter ?? "", school: user?.school ?? "",
  });
  const [ok, setOk] = useState("");
  const [error, setError] = useState("");
  const [photoKey, setPhotoKey] = useState(0);
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }));

  async function save(e: FormEvent) {
    e.preventDefault();
    setOk("");
    setError("");
    try {
      await api<User>("/profile", {
        method: "PATCH",
        body: { ...f, grade: Number(f.grade), middle_name: f.middle_name || null },
      });
      await refresh();
      setOk("Профиль сохранён");
    } catch (err) {
      setError(errText(err));
    }
  }

  async function upload(file: File | undefined) {
    if (!file) return;
    setOk("");
    setError("");
    const form = new FormData();
    form.append("file", file);
    try {
      await api<User>("/profile/photo", { form });
      await refresh();
      setPhotoKey((k) => k + 1);
    } catch (err) {
      setError(errText(err));
    }
  }

  async function removePhoto() {
    await api("/profile/photo", { method: "DELETE" });
    await refresh();
    setPhotoKey((k) => k + 1);
  }

  if (!user) return null;
  return (
    <>
      <PageTitle sub={user.email}>Профиль</PageTitle>
      {ok && <Alert kind="ok">{ok}</Alert>}
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-5 md:grid-cols-3">
        <section className="card text-center">
          <div className="mx-auto mb-3 flex h-36 w-36 items-center justify-center overflow-hidden rounded-full border-2 border-ink bg-sand">
            {user.has_photo ? (
              <img key={photoKey} src={`/api/profile/photo?v=${photoKey}`} alt="Фото профиля" className="h-full w-full object-cover" />
            ) : (
              <span className="font-serif text-4xl text-soft">{user.first_name[0]}{user.last_name[0]}</span>
            )}
          </div>
          <label className="btn btn-ghost btn-sm cursor-pointer">
            Загрузить фото
            <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
          </label>
          {user.has_photo && <button className="btn btn-ghost btn-sm ml-2" onClick={removePhoto}>Удалить</button>}
          <p className="mt-2 text-xs text-soft">Необязательно. JPG, PNG или WEBP до 2 МБ.</p>
        </section>

        <form onSubmit={save} className="card space-y-3 md:col-span-2">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Фамилия"><input required value={f.last_name} onChange={(e) => set("last_name", e.target.value)} /></Field>
            <Field label="Имя"><input required value={f.first_name} onChange={(e) => set("first_name", e.target.value)} /></Field>
          </div>
          <Field label="Отчество"><input value={f.middle_name} onChange={(e) => set("middle_name", e.target.value)} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Класс">
              <select value={f.grade} onChange={(e) => set("grade", e.target.value)}>
                {Array.from({ length: 11 }, (_, i) => i + 1).map((g) => <option key={g}>{g}</option>)}
              </select>
            </Field>
            <Field label="Буква"><input maxLength={2} value={f.class_letter} onChange={(e) => set("class_letter", e.target.value)} /></Field>
          </div>
          <Field label="Школа"><input value={f.school} onChange={(e) => set("school", e.target.value)} /></Field>
          <button className="btn btn-rust">Сохранить</button>
        </form>
      </div>
    </>
  );
}
