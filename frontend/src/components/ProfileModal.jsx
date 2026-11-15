import { useEffect, useState } from "react";
import { KeyRound, Save, User, X } from "lucide-react";
import { apiFetch } from "../api/client";

export default function ProfileModal({ open, onClose, onProfileUpdated }) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [profile, setProfile] = useState(null);
  const [form, setForm] = useState({ ho_ten: "", sdt: "", email: "", dia_chi: "" });
  const [pwForm, setPwForm] = useState({ current_password: "", new_password: "" });
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError("");
    setMsg("");
    apiFetch("/api/auth/profile")
      .then((data) => {
        setProfile(data);
        const d = data.detail || {};
        setForm({
          ho_ten: d.HoTen || "",
          sdt: d.SDT || "",
          email: d.Email || data.Email || "",
          dia_chi: d.DiaChi || "",
        });
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  async function handleSaveProfile(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMsg("");
    try {
      const payload = {
        sdt: form.sdt || undefined,
        email: form.email || undefined,
      };
      if (profile?.MaKH) {
        payload.ho_ten = form.ho_ten || undefined;
        payload.dia_chi = form.dia_chi;
      }
      const res = await apiFetch("/api/auth/profile", {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      setMsg(res.message);
      onProfileUpdated?.(res.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMsg("");
    try {
      const res = await apiFetch("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify(pwForm),
      });
      setMsg(res.message);
      setPwForm({ current_password: "", new_password: "" });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl border border-stone-200 overflow-hidden max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 bg-stone-900 text-white">
          <div className="flex items-center gap-2">
            <User className="w-5 h-5 text-amber-400" />
            <h2 className="font-semibold text-base">Hồ sơ cá nhân &amp; Bảo mật</h2>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-stone-800 text-stone-300">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="rounded-xl bg-rose-50 border border-rose-200 px-3 py-2 text-xs text-rose-700">
              {error}
            </div>
          )}
          {msg && (
            <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-700">
              {msg}
            </div>
          )}

          {loading ? (
            <p className="text-sm text-stone-500">Đang tải thông tin...</p>
          ) : (
            <>
              <form onSubmit={handleSaveProfile} className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-stone-500">
                  Thông tin tài khoản ({profile?.TenDangNhap})
                </p>

                {profile?.MaKH && (
                  <label className="block text-xs font-medium text-stone-700">
                    Họ tên
                    <input
                      required
                      value={form.ho_ten}
                      onChange={(e) => setForm({ ...form, ho_ten: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    />
                  </label>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label className="block text-xs font-medium text-stone-700">
                    Số điện thoại
                    <input
                      value={form.sdt}
                      onChange={(e) => setForm({ ...form, sdt: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    />
                  </label>
                  <label className="block text-xs font-medium text-stone-700">
                    Email
                    <input
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    />
                  </label>
                </div>

                {profile?.MaKH && (
                  <label className="block text-xs font-medium text-stone-700">
                    Địa chỉ
                    <input
                      value={form.dia_chi}
                      onChange={(e) => setForm({ ...form, dia_chi: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    />
                  </label>
                )}

                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 text-white px-4 py-2 text-xs font-semibold disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5 text-amber-400" /> Lưu thông tin liên hệ
                </button>
              </form>

              <hr className="border-stone-200" />

              <form onSubmit={handleChangePassword} className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-stone-500 flex items-center gap-1">
                  <KeyRound className="w-3.5 h-3.5 text-amber-600" /> Đổi mật khẩu
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <label className="block text-xs font-medium text-stone-700">
                    Mật khẩu hiện tại
                    <input
                      type="password"
                      required
                      value={pwForm.current_password}
                      onChange={(e) => setPwForm({ ...pwForm, current_password: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    />
                  </label>
                  <label className="block text-xs font-medium text-stone-700">
                    Mật khẩu mới (≥ 6 ký tự)
                    <input
                      type="password"
                      required
                      minLength={6}
                      value={pwForm.new_password}
                      onChange={(e) => setPwForm({ ...pwForm, new_password: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
                    />
                  </label>
                </div>
                <button
                  type="submit"
                  disabled={saving}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 text-xs font-semibold disabled:opacity-50"
                >
                  Cập nhật mật khẩu
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
