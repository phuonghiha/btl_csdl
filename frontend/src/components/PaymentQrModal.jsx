import { useEffect, useRef, useState } from "react";
import { Check, CheckCircle2, Copy, QrCode, Radio, X } from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { apiFetch } from "../api/client";
import { formatVND } from "../utils/format";

export default function PaymentQrModal({
  maHd,
  initialQr = null,
  canConfirmPayment = false,
  onClose,
  onPaid,
}) {
  const [mode, setMode] = useState("full");
  const [qrData, setQrData] = useState(initialQr);
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [copiedKey, setCopiedKey] = useState("");
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const knownPaidRef = useRef(0);

  useEffect(() => {
    setQrData(initialQr);
    knownPaidRef.current = Number(initialQr?.da_thu || 0);
    setMode("full");
    setMsg("");
    setError("");
  }, [maHd, initialQr]);

  useEffect(() => {
    if (!maHd) return;
    if (mode === "full" && initialQr && initialQr.ma_hd === maHd) {
      setQrData(initialQr);
      knownPaidRef.current = Number(initialQr.da_thu || 0);
      return;
    }
    setLoading(true);
    setError("");
    apiFetch(`/api/invoices/${maHd}/payment-qr?mode=${mode}`)
      .then((data) => {
        setQrData(data);
        knownPaidRef.current = Number(data?.da_thu || 0);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [maHd, mode]);

  useEffect(() => {
    if (!maHd || !qrData || qrData.con_phai_tra <= 0) return;
    let cancelled = false;

    const timer = setInterval(async () => {
      try {
        const st = await apiFetch(`/api/invoices/${maHd}/payment-status`);
        if (cancelled) return;
        const newPaid = Number(st.da_thu || 0);
        if (newPaid > knownPaidRef.current) {
          const delta = newPaid - knownPaidRef.current;
          knownPaidRef.current = newPaid;
          const txCode = st.latest_payment?.MaGiaoDichCong;
          const updated = await apiFetch(`/api/invoices/${maHd}/payment-qr?mode=${mode}`);
          if (cancelled) return;
          setQrData(updated);
          setMsg(
            `Đã tự động nhận ${formatVND(delta)} qua VietQR${txCode ? ` (${txCode})` : ""}!`
          );
          onPaid?.();
        }
      } catch {
        // Ignore transient poll errors while waiting
      }
    }, 2500);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [maHd, mode, qrData?.con_phai_tra]);

  if (!maHd) return null;

  function copyText(key, text) {
    navigator.clipboard?.writeText(String(text));
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(""), 1500);
  }

  async function handleConfirmTransfer() {
    if (!qrData || qrData.so_tien_chuyen <= 0) return;
    setConfirming(true);
    setError("");
    setMsg("");
    try {
      await apiFetch(`/api/invoices/${maHd}/payments`, {
        method: "POST",
        body: JSON.stringify({
          cong_thanh_toan: "CHUYEN_KHOAN",
          ma_giao_dich_cong: `QR-${maHd}-${Date.now().toString().slice(-6)}`,
          so_tien: qrData.so_tien_chuyen,
          noi_dung: qrData.noi_dung,
        }),
      });
      setMsg(`Đã xác nhận thu ${formatVND(qrData.so_tien_chuyen)} qua chuyển khoản QR!`);
      const updated = await apiFetch(`/api/invoices/${maHd}/payment-qr?mode=full`);
      knownPaidRef.current = Number(updated?.da_thu || 0);
      setQrData(updated);
      onPaid?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/55 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl bg-white shadow-2xl border border-stone-200 overflow-hidden max-h-[92vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 bg-stone-900 text-white">
          <div className="flex items-center gap-2">
            <QrCode className="w-5 h-5 text-amber-400" />
            <div>
              <h3 className="font-semibold text-sm">
                Mã QR Chuyển khoản Thanh toán — HĐ #{maHd}
              </h3>
              {qrData?.ma_dp && (
                <p className="text-[11px] text-stone-300">
                  Đơn đặt phòng #{qrData.ma_dp} · {qrData.ten_cn}
                </p>
              )}
            </div>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-stone-800 text-stone-300">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Mode Switch */}
          <div className="grid grid-cols-2 gap-2 rounded-xl bg-stone-100 p-1">
            <button
              type="button"
              onClick={() => setMode("full")}
              className={`py-2 rounded-lg text-xs font-semibold transition-colors ${
                mode === "full"
                  ? "bg-white text-stone-900 shadow-xs"
                  : "text-stone-600 hover:text-stone-900"
              }`}
            >
              Thanh toán 100% còn lại
            </button>
            <button
              type="button"
              onClick={() => setMode("deposit")}
              className={`py-2 rounded-lg text-xs font-semibold transition-colors ${
                mode === "deposit"
                  ? "bg-white text-stone-900 shadow-xs"
                  : "text-stone-600 hover:text-stone-900"
              }`}
            >
              Đặt cọc nhanh 30%
            </button>
          </div>

          {error && (
            <div className="rounded-xl bg-rose-50 border border-rose-200 px-3 py-2 text-xs text-rose-700">
              {error}
            </div>
          )}
          {msg && (
            <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2.5 text-xs text-emerald-800 flex items-center gap-2 font-medium">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              {msg}
            </div>
          )}

          {loading || !qrData ? (
            <p className="py-10 text-center text-sm text-stone-500">Đang tạo mã QR chuyển khoản...</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 items-center">
              {/* QR Code Box */}
              <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-amber-200 bg-gradient-to-b from-amber-50/50 to-white p-4">
                <span className="text-[11px] font-bold tracking-wider uppercase text-amber-800 mb-2">
                  VietQR · NAPAS 247
                </span>
                <div className="bg-white p-2.5 rounded-xl border border-stone-200 shadow-xs">
                  <QRCodeSVG value={qrData.vietqr_payload} size={172} level="M" />
                </div>
                <p className="text-[11px] text-stone-500 mt-2 text-center">
                  Quét bằng app ngân hàng bất kỳ
                </p>
                {qrData.con_phai_tra > 0 && (
                  <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-medium text-emerald-700">
                    <Radio className="w-3 h-3 animate-pulse" />
                    Tự động cập nhật khi tiền về
                  </div>
                )}
                <div className="mt-2.5 flex flex-wrap items-center justify-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => copyText("payload", qrData.vietqr_payload)}
                    className="inline-flex items-center gap-1 rounded-lg border border-stone-300 bg-white hover:bg-stone-100 px-2 py-1 text-[11px] font-medium text-stone-700"
                  >
                    {copiedKey === "payload" ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-600" /> Đã chép chuỗi QR
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" /> Chép chuỗi QR
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Transfer Details */}
              <div className="space-y-2.5 text-xs">
                <div className="rounded-xl bg-stone-50 border border-stone-200 p-3 space-y-2">
                  <div>
                    <span className="text-stone-500 block">Ngân hàng thụ hưởng</span>
                    <strong className="text-stone-900">{qrData.bank_name}</strong>
                  </div>
                  <div>
                    <span className="text-stone-500 block">Chủ tài khoản</span>
                    <strong className="text-stone-900">{qrData.account_name}</strong>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <span className="text-stone-500 block">Số tài khoản</span>
                      <strong className="font-mono text-sm text-stone-900">
                        {qrData.account_no}
                      </strong>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyText("stk", qrData.account_no)}
                      className="p-1.5 rounded-md border border-stone-300 bg-white hover:bg-stone-100"
                      title="Sao chép STK"
                    >
                      {copiedKey === "stk" ? (
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <Copy className="w-3.5 h-3.5 text-stone-600" />
                      )}
                    </button>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-1 border-t border-stone-200">
                    <div>
                      <span className="text-stone-500 block">Số tiền cần chuyển</span>
                      <strong className="text-base text-amber-700">
                        {formatVND(qrData.so_tien_chuyen)}
                      </strong>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyText("amt", qrData.so_tien_chuyen)}
                      className="p-1.5 rounded-md border border-stone-300 bg-white hover:bg-stone-100"
                      title="Sao chép số tiền"
                    >
                      {copiedKey === "amt" ? (
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <Copy className="w-3.5 h-3.5 text-stone-600" />
                      )}
                    </button>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-1 border-t border-stone-200">
                    <div>
                      <span className="text-stone-500 block">Nội dung chuyển khoản</span>
                      <strong className="font-mono text-stone-900">{qrData.noi_dung}</strong>
                    </div>
                    <button
                      type="button"
                      onClick={() => copyText("memo", qrData.noi_dung)}
                      className="p-1.5 rounded-md border border-stone-300 bg-white hover:bg-stone-100"
                      title="Sao chép nội dung CK"
                    >
                      {copiedKey === "memo" ? (
                        <Check className="w-3.5 h-3.5 text-emerald-600" />
                      ) : (
                        <Copy className="w-3.5 h-3.5 text-stone-600" />
                      )}
                    </button>
                  </div>
                </div>

                <p className="text-[11px] text-stone-500 leading-relaxed">
                  Tổng HĐ: {formatVND(qrData.tong_tien)} · Đã thu: {formatVND(qrData.da_thu)} · Còn lại:{" "}
                  <strong className="text-stone-800">{formatVND(qrData.con_phai_tra)}</strong>
                </p>
              </div>
            </div>
          )}

          {/* Action Footer */}
          {qrData && (
            <div className="pt-2 border-t border-stone-200 flex flex-col sm:flex-row items-center justify-between gap-3">
              {canConfirmPayment && qrData.so_tien_chuyen > 0 ? (
                <button
                  type="button"
                  disabled={confirming}
                  onClick={handleConfirmTransfer}
                  className="w-full sm:w-auto flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2.5 text-xs font-semibold disabled:opacity-50"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  {confirming
                    ? "Đang ghi nhận..."
                    : `Xác nhận đã nhận chuyển khoản (${formatVND(qrData.so_tien_chuyen)})`}
                </button>
              ) : (
                <p className="text-[11px] text-stone-500">
                  {qrData.con_phai_tra <= 0
                    ? "Hóa đơn này đã được thanh toán đủ."
                    : "Giữ đúng nội dung chuyển khoản để lễ tân đối soát và xác nhận đơn."}
                </p>
              )}
              <button
                type="button"
                onClick={onClose}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-stone-300 text-xs font-medium text-stone-700 hover:bg-stone-50"
              >
                Đóng
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
