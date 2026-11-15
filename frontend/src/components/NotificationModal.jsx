import { useState } from "react";
import { Bell, CheckCircle2, Copy, KeyRound, QrCode, RefreshCw, Sparkles, X, XCircle } from "lucide-react";
import { apiFetch } from "../api/client";

export default function NotificationModal({
  open,
  notifications = [],
  loading = false,
  onClose,
  onRefresh,
  onOpenPaymentQr,
}) {
  const [busyId, setBusyId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  if (!open) return null;

  async function handleRespond(maTb, action) {
    setError("");
    setNotice("");
    setBusyId(maTb);
    try {
      const res = await apiFetch(`/api/notifications/${maTb}/respond`, {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      setNotice(res.message || (action === "confirm" ? "Đã xác nhận" : "Đã từ chối"));
      if (onRefresh) await onRefresh();
      if (action === "confirm" && res.MaHD && onOpenPaymentQr) {
        onOpenPaymentQr(res.MaHD, res.payment_qr || null);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  function handleCopyOtp(maTb, otp) {
    if (!otp) return;
    navigator.clipboard?.writeText(otp);
    setCopiedId(maTb);
    setTimeout(() => setCopiedId(null), 1500);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4 backdrop-blur-xs">
      <div className="w-full max-w-xl max-h-[85vh] flex flex-col rounded-2xl bg-white shadow-2xl border border-stone-200 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 bg-stone-900 text-white">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Bell className="w-4 h-4 text-amber-400" />
            Thông báo &amp; Xác nhận trên thiết bị khách hàng
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onRefresh}
              disabled={loading}
              className="p-1.5 rounded-lg hover:bg-stone-800 text-stone-300 hover:text-white"
              title="Làm mới thông báo"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button type="button" onClick={onClose} className="p-1 rounded-lg hover:bg-stone-800">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="p-5 overflow-y-auto space-y-3">
          {error && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 px-3 py-2 text-xs text-rose-700">
              {error}
            </div>
          )}
          {notice && (
            <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-800">
              {notice}
            </div>
          )}

          {notifications.length === 0 ? (
            <div className="py-12 text-center text-sm text-stone-500">
              Chưa có thông báo xác thực OTP hay đề xuất dịch vụ nào.
            </div>
          ) : (
            notifications.map((tb) => {
              const isPending = tb.TrangThai === "Chờ xác nhận";
              const isOtp = tb.LoaiTB === "CANCEL_OTP";
              const isService = tb.LoaiTB === "SERVICE_CONFIRM";
              return (
                <div
                  key={tb.MaTB}
                  className={`rounded-xl border p-4 space-y-2.5 ${
                    isPending
                      ? isOtp
                        ? "border-amber-300 bg-amber-50/70"
                        : "border-emerald-300 bg-emerald-50/60"
                      : "border-stone-200 bg-stone-50 opacity-80"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      {isOtp ? (
                        <KeyRound className="w-4 h-4 text-amber-700 shrink-0" />
                      ) : (
                        <Sparkles className="w-4 h-4 text-emerald-700 shrink-0" />
                      )}
                      <div>
                        <h4 className="text-sm font-bold text-stone-900">{tb.TieuDe}</h4>
                        <p className="text-[11px] text-stone-500">
                          Đơn #{tb.MaDP} · {tb.ThoiGianTao ? String(tb.ThoiGianTao).replace("T", " ").slice(0, 16) : ""}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
                        isPending
                          ? "bg-amber-200 text-amber-900"
                          : tb.TrangThai === "Đã xác nhận"
                          ? "bg-emerald-200 text-emerald-900"
                          : "bg-stone-200 text-stone-700"
                      }`}
                    >
                      {tb.TrangThai}
                    </span>
                  </div>

                  <p className="text-xs text-stone-700 leading-relaxed">{tb.NoiDung}</p>

                  {isOtp && tb.OtpCode && isPending && (
                    <div className="flex items-center justify-between gap-2 rounded-xl bg-white border border-amber-300 px-3.5 py-2.5">
                      <div>
                        <p className="text-[10px] uppercase tracking-wider text-stone-500 font-semibold">
                          Mã OTP hủy đơn (cung cấp cho lễ tân)
                        </p>
                        <p className="text-xl font-bold font-mono tracking-[0.25em] text-amber-800">
                          {tb.OtpCode}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleCopyOtp(tb.MaTB, tb.OtpCode)}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-stone-200 bg-stone-50 hover:bg-stone-100 text-xs font-medium text-stone-700"
                      >
                        <Copy className="w-3.5 h-3.5" />
                        {copiedId === tb.MaTB ? "Đã chép" : "Chép OTP"}
                      </button>
                    </div>
                  )}

                  {isPending && (
                    <div className="flex flex-wrap justify-end gap-2 pt-1">
                      <button
                        type="button"
                        disabled={busyId === tb.MaTB}
                        onClick={() => handleRespond(tb.MaTB, "reject")}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-rose-200 bg-white hover:bg-rose-50 text-xs font-semibold text-rose-700 disabled:opacity-50"
                      >
                        <XCircle className="w-3.5 h-3.5" /> Từ chối
                      </button>
                      {isService && (
                        <button
                          type="button"
                          disabled={busyId === tb.MaTB}
                          onClick={() => handleRespond(tb.MaTB, "confirm")}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold disabled:opacity-50"
                        >
                          <QrCode className="w-3.5 h-3.5" />
                          {busyId === tb.MaTB ? "Đang xử lý..." : "Xác nhận & Thanh toán QR"}
                        </button>
                      )}
                      {!isService && !isOtp && (
                        <button
                          type="button"
                          disabled={busyId === tb.MaTB}
                          onClick={() => handleRespond(tb.MaTB, "confirm")}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" /> Đã hiểu
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
