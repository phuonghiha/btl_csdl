import { useEffect, useState } from "react";
import { AlertTriangle, KeyRound, Send, X } from "lucide-react";
import { apiFetch } from "../api/client";

const QUICK_REASONS = [
  "Khách thay đổi kế hoạch",
  "Đổi ngày nhận phòng / chi nhánh",
  "Khách không xác nhận cọc đúng hạn",
];

export default function CancelBookingModal({ maDp, requireOtp = false, onClose, onConfirm }) {
  const [reason, setReason] = useState(QUICK_REASONS[0]);
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [sendingOtp, setSendingOtp] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setReason(QUICK_REASONS[0]);
    setOtpSent(false);
    setOtpCode("");
    setStatusMsg("");
    setErrorMsg("");
  }, [maDp, requireOtp]);

  if (!maDp) return null;

  async function handleSendOtp() {
    setErrorMsg("");
    setStatusMsg("");
    setSendingOtp(true);
    try {
      const res = await apiFetch(`/api/bookings/${maDp}/cancel-otp`, {
        method: "POST",
        body: JSON.stringify({ ly_do: reason.trim() || QUICK_REASONS[0] }),
      });
      setOtpSent(true);
      setStatusMsg(res.message || "Đã gửi mã OTP 6 số tới thông báo trên tài khoản khách hàng.");
    } catch (err) {
      setErrorMsg(err.message);
    } finally {
      setSendingOtp(false);
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!reason.trim()) return;
    if (requireOtp && !otpCode.trim()) {
      setErrorMsg("Vui lòng gửi OTP và nhập mã OTP xác thực từ thiết bị khách hàng.");
      return;
    }
    setErrorMsg("");
    setBusy(true);
    try {
      await onConfirm(maDp, reason.trim(), requireOtp ? otpCode.trim() : undefined);
      onClose();
    } catch (err) {
      setErrorMsg(err.message || "Không thể hủy đơn đặt phòng");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4 backdrop-blur-xs">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-md rounded-2xl bg-white shadow-2xl border border-stone-200 overflow-hidden"
      >
        <div className="flex items-center justify-between px-5 py-3.5 bg-rose-900 text-white">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <AlertTriangle className="w-4 h-4 text-amber-300" />
            Xác nhận hủy đơn đặt phòng #{maDp}
          </div>
          <button type="button" onClick={onClose} className="p-1 rounded-lg hover:bg-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {QUICK_REASONS.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setReason(r)}
                className={`px-2.5 py-1 rounded-full text-xs border ${reason === r
                  ? "bg-rose-50 border-rose-300 text-rose-700 font-medium"
                  : "bg-stone-50 border-stone-200 text-stone-600 hover:bg-stone-100"
                  }`}
              >
                {r}
              </button>
            ))}
          </div>

          <label className="block text-xs font-medium text-stone-700">
            Lý do hủy đơn
            <textarea
              required
              minLength={3}
              rows={2}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </label>

          {requireOtp && (
            <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3 space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-amber-900 flex items-center gap-1.5">
                  <KeyRound className="w-3.5 h-3.5 text-amber-700" />
                  Xác thực OTP từ máy khách
                </span>
                <button
                  type="button"
                  disabled={sendingOtp}
                  onClick={handleSendOtp}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold disabled:opacity-50"
                >
                  <Send className="w-3 h-3" />
                  {sendingOtp ? "Đang gửi..." : otpSent ? "Gửi lại OTP" : "Gửi OTP về máy khách"}
                </button>
              </div>
              <p className="text-[11px] text-amber-800">
                Hệ thống sẽ gửi thông báo kèm mã OTP 6 số đến tài khoản khách hàng. Nhập mã OTP khách cung cấp để hoàn tất hủy đơn.
              </p>
              <input
                type="text"
                inputMode="numeric"
                maxLength={6}
                required
                placeholder="Nhập mã OTP 6 số (ví dụ: 482910)"
                value={otpCode}
                onChange={(e) => setOtpCode(e.target.value.replace(/\s+/g, ""))}
                className="w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-mono tracking-widest"
              />
            </div>
          )}

          {statusMsg && (
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-800">
              {statusMsg}
            </div>
          )}
          {errorMsg && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 px-3 py-2 text-xs text-rose-700">
              {errorMsg}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-stone-300 text-xs font-medium text-stone-700"
            >
              Giữ lại đơn
            </button>
            <button
              type="submit"
              disabled={busy}
              className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold disabled:opacity-50"
            >
              {busy ? "Đang xử lý..." : "Xác nhận hủy"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
