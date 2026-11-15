import { useState } from "react";
import { KeyRound, ShieldCheck, UserPlus, X } from "lucide-react";
import { apiFetch, setStoredToken } from "../api/client";

const DEMO_ACCOUNTS = [
  { username: "admin_hethong", label: "Admin Hệ thống", desc: "Toàn quyền 10 chi nhánh" },
  { username: "quanly_cn1", label: "Quản lý CN 1", desc: "Hà Nội — Quản lý & Báo cáo" },
  { username: "letan_cn1", label: "Lễ tân CN 1", desc: "Hà Nội — Check-in/out & Thu tiền" },
  { username: "dichvu_cn2", label: "NV Dịch vụ CN 2", desc: "Đà Nẵng — Dịch vụ & Quét vé QR" },
  { username: "khach_an", label: "Khách hàng", desc: "Nguyễn Văn An — Đặt phòng" },
];

export default function LoginModal({ open, onClose, onSuccess }) {
  const [tab, setTab] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [regForm, setRegForm] = useState({
    username: "",
    password: "",
    ho_ten: "",
    cccd: "",
    sdt: "",
    email: "",
    dia_chi: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (!open) return null;

  async function doLogin(u, p) {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: u, password: p }),
      });
      setStoredToken(data.access_token);
      onSuccess(data.user);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleLoginSubmit(e) {
    e.preventDefault();
    await doLogin(username, password);
  }

  async function handleRegisterSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(regForm),
      });
      setStoredToken(data.access_token);
      onSuccess(data.user);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl border border-stone-200 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 bg-stone-900 text-white">
          <div className="flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-amber-400" />
            <h2 className="font-semibold text-base">
              {tab === "login" ? "Đăng nhập hệ thống" : "Đăng ký tài khoản khách hàng"}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-stone-800 text-stone-300"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex border-b border-stone-200 bg-stone-50">
          <button
            type="button"
            onClick={() => {
              setTab("login");
              setError("");
            }}
            className={`flex-1 py-2.5 text-sm font-medium ${
              tab === "login"
                ? "bg-white text-stone-900 border-b-2 border-amber-600"
                : "text-stone-500 hover:text-stone-800"
            }`}
          >
            Đăng nhập
          </button>
          <button
            type="button"
            onClick={() => {
              setTab("register");
              setError("");
            }}
            className={`flex-1 py-2.5 text-sm font-medium flex items-center justify-center gap-1.5 ${
              tab === "register"
                ? "bg-white text-stone-900 border-b-2 border-amber-600"
                : "text-stone-500 hover:text-stone-800"
            }`}
          >
            <UserPlus className="w-4 h-4" /> Đăng ký khách mới
          </button>
        </div>

        <div className="p-6 space-y-5 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="rounded-xl bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3 text-sm">
              {error}
            </div>
          )}

          {tab === "login" ? (
            <>
              <form onSubmit={handleLoginSubmit} className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">
                    Tên đăng nhập
                  </label>
                  <input
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Ví dụ: admin_hethong"
                    className="w-full rounded-xl border border-stone-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">
                    Mật khẩu
                  </label>
                  <input
                    required
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full rounded-xl border border-stone-300 px-3.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500"
                  />
                </div>
                <button
                  disabled={loading}
                  type="submit"
                  className="w-full rounded-xl bg-stone-900 hover:bg-stone-800 text-white py-2.5 text-sm font-medium disabled:opacity-50 cursor-pointer"
                >
                  {loading ? "Đang đăng nhập..." : "Đăng nhập"}
                </button>
              </form>

              <div className="border-t border-stone-200 pt-4">
                <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-stone-500 mb-2.5">
                  <ShieldCheck className="w-4 h-4 text-amber-600" />
                  Đăng nhập nhanh 5 vai trò demo (Mật khẩu: Demo@123456)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {DEMO_ACCOUNTS.map((acc) => (
                    <button
                      key={acc.username}
                      type="button"
                      disabled={loading}
                      onClick={() => doLogin(acc.username, "Demo@123456")}
                      className="text-left rounded-xl border border-stone-200 hover:border-amber-500 hover:bg-amber-50/50 px-3 py-2 transition cursor-pointer"
                    >
                      <div className="text-xs font-semibold text-stone-900">
                        {acc.label}
                      </div>
                      <div className="text-[11px] text-stone-500">{acc.desc}</div>
                    </button>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <form onSubmit={handleRegisterSubmit} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">
                    Tên đăng nhập *
                  </label>
                  <input
                    required
                    minLength={3}
                    value={regForm.username}
                    onChange={(e) => setRegForm({ ...regForm, username: e.target.value })}
                    className="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">
                    Mật khẩu *
                  </label>
                  <input
                    required
                    minLength={6}
                    type="password"
                    value={regForm.password}
                    onChange={(e) => setRegForm({ ...regForm, password: e.target.value })}
                    className="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-600 mb-1">
                  Họ và tên *
                </label>
                <input
                  required
                  value={regForm.ho_ten}
                  onChange={(e) => setRegForm({ ...regForm, ho_ten: e.target.value })}
                  className="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">
                    CCCD *
                  </label>
                  <input
                    required
                    value={regForm.cccd}
                    onChange={(e) => setRegForm({ ...regForm, cccd: e.target.value })}
                    className="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-stone-600 mb-1">
                    Số điện thoại *
                  </label>
                  <input
                    required
                    value={regForm.sdt}
                    onChange={(e) => setRegForm({ ...regForm, sdt: e.target.value })}
                    className="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-600 mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={regForm.email}
                  onChange={(e) => setRegForm({ ...regForm, email: e.target.value })}
                  className="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-stone-600 mb-1">
                  Địa chỉ
                </label>
                <input
                  value={regForm.dia_chi}
                  onChange={(e) => setRegForm({ ...regForm, dia_chi: e.target.value })}
                  className="w-full rounded-xl border border-stone-300 px-3 py-2 text-sm"
                />
              </div>
              <button
                disabled={loading}
                type="submit"
                className="w-full rounded-xl bg-amber-600 hover:bg-amber-700 text-white py-2.5 text-sm font-medium cursor-pointer"
              >
                {loading ? "Đang tạo tài khoản..." : "Đăng ký & Đăng nhập"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
