import { useEffect, useState } from "react";
import { CreditCard, Printer, QrCode, Receipt, Tag, X } from "lucide-react";
import { apiFetch } from "../api/client";
import { formatDateTime, formatVND } from "../utils/format";
import Badge from "./Badge";
import PaymentQrModal from "./PaymentQrModal";

export default function InvoiceModal({ maHd, canManage, onClose, onUpdated }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showQr, setShowQr] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const [payForm, setPayForm] = useState({
    cong_thanh_toan: "VNPAY",
    ma_giao_dich_cong: "",
    so_tien: "",
    noi_dung: "",
  });
  const [voucherCode, setVoucherCode] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadDetail() {
    setLoading(true);
    setError("");
    try {
      const data = await apiFetch(`/api/invoices/${maHd}`);
      setDetail(data);
      const daThu = (data.payments || [])
        .filter((p) => p.TrangThai === "Thành công")
        .reduce((acc, p) => acc + Number(p.SoTien || 0), 0);
      const conLai = Math.max(0, Number(data.invoice.TongTien || 0) - daThu);
      setPayForm((prev) => ({
        ...prev,
        so_tien: conLai > 0 ? String(conLai) : "",
        ma_giao_dich_cong: `GD-${maHd}-${Date.now().toString().slice(-6)}`,
        noi_dung: `Thanh toan hoa don #${maHd}`,
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (maHd) loadDetail();
  }, [maHd]);

  if (!maHd) return null;

  const daThu = (detail?.payments || [])
    .filter((p) => p.TrangThai === "Thành công")
    .reduce((acc, p) => acc + Number(p.SoTien || 0), 0);
  const tongTien = Number(detail?.invoice?.TongTien || 0);
  const conLai = Math.max(0, tongTien - daThu);

  async function handlePayment(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMsg("");
    try {
      await apiFetch(`/api/invoices/${maHd}/payments`, {
        method: "POST",
        body: JSON.stringify({
          ...payForm,
          so_tien: Number(payForm.so_tien),
        }),
      });
      setMsg("Đã ghi nhận thanh toán thành công!");
      await loadDetail();
      onUpdated?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleApplyVoucher(e) {
    e.preventDefault();
    if (!voucherCode.trim()) return;
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const res = await apiFetch(`/api/invoices/${maHd}/apply-voucher`, {
        method: "POST",
        body: JSON.stringify({ code: voucherCode.trim() }),
      });
      setMsg(`Áp mã thành công — Giảm ${formatVND(res.SoTienGiam)}`);
      setVoucherCode("");
      await loadDetail();
      onUpdated?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4">
      <div className="w-full max-w-3xl rounded-2xl bg-white shadow-2xl border border-stone-200 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 bg-stone-900 text-white">
          <div className="flex items-center gap-2">
            <Receipt className="w-5 h-5 text-amber-400" />
            <h3 className="font-semibold">Chi tiết Hóa đơn #{maHd}</h3>
          </div>
          <div className="flex items-center gap-1.5 print:hidden">
            {conLai > 0 && (
              <button
                type="button"
                onClick={() => setShowQr(true)}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-xs font-semibold text-white"
              >
                <QrCode className="w-3.5 h-3.5" /> QR Chuyển tiền
              </button>
            )}
            <button
              type="button"
              onClick={() => window.print()}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-stone-800 hover:bg-stone-700 text-xs text-stone-200"
              title="In hóa đơn"
            >
              <Printer className="w-3.5 h-3.5" /> In
            </button>
            <button onClick={onClose} className="p-1 rounded-lg hover:bg-stone-800">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="p-6 max-h-[82vh] overflow-y-auto space-y-5">
          {loading ? (
            <p className="text-sm text-stone-500">Đang tải hóa đơn...</p>
          ) : detail ? (
            <>
              {error && (
                <div className="rounded-xl bg-rose-50 border border-rose-200 text-rose-700 px-4 py-2.5 text-sm">
                  {error}
                </div>
              )}
              {msg && (
                <div className="rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-2.5 text-sm">
                  {msg}
                </div>
              )}

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-stone-50 rounded-xl p-4 border border-stone-200">
                <div>
                  <div className="text-xs text-stone-500">Tổng hóa đơn</div>
                  <div className="font-bold text-stone-900">{formatVND(tongTien)}</div>
                </div>
                <div>
                  <div className="text-xs text-stone-500">Đã thanh toán</div>
                  <div className="font-bold text-emerald-700">{formatVND(daThu)}</div>
                </div>
                <div>
                  <div className="text-xs text-stone-500">Còn phải trả</div>
                  <div className="font-bold text-rose-700">{formatVND(conLai)}</div>
                </div>
                <div>
                  <div className="text-xs text-stone-500 mb-1">Trạng thái</div>
                  <Badge status={detail.invoice.TrangThai} />
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
                  Chi tiết khoản thu (CT_HOA_DON)
                </h4>
                <div className="border border-stone-200 rounded-xl overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-stone-50 text-stone-600 text-xs">
                      <tr>
                        <th className="text-left px-3 py-2">Loại</th>
                        <th className="text-left px-3 py-2">Mô tả</th>
                        <th className="text-right px-3 py-2">SL</th>
                        <th className="text-right px-3 py-2">Đơn giá</th>
                        <th className="text-right px-3 py-2">Thành tiền</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {detail.items.map((it) => (
                        <tr key={it.MaCTHD}>
                          <td className="px-3 py-2 text-xs font-medium text-stone-700">
                            {it.LoaiKhoanThu}
                          </td>
                          <td className="px-3 py-2">{it.MoTa}</td>
                          <td className="px-3 py-2 text-right">{Number(it.SoLuong)}</td>
                          <td className="px-3 py-2 text-right">{formatVND(it.DonGia)}</td>
                          <td className="px-3 py-2 text-right font-medium">
                            {formatVND(Number(it.SoLuong) * Number(it.DonGia))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <h4 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
                  Lịch sử giao dịch (GIAO_DICH_THANH_TOAN)
                </h4>
                {detail.payments.length === 0 ? (
                  <p className="text-sm text-stone-500 italic">Chưa có giao dịch nào.</p>
                ) : (
                  <div className="border border-stone-200 rounded-xl overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-stone-50 text-stone-600 text-xs">
                        <tr>
                          <th className="text-left px-3 py-2">Cổng / Hình thức</th>
                          <th className="text-left px-3 py-2">Mã GD</th>
                          <th className="text-left px-3 py-2">Thời gian</th>
                          <th className="text-right px-3 py-2">Số tiền</th>
                          <th className="text-left px-3 py-2">Trạng thái</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {detail.payments.map((p) => (
                          <tr key={p.MaGiaoDich}>
                            <td className="px-3 py-2 font-medium">{p.CongThanhToan}</td>
                            <td className="px-3 py-2 text-xs text-stone-600">
                              {p.MaGiaoDichCong || "—"}
                            </td>
                            <td className="px-3 py-2 text-xs text-stone-600">
                              {formatDateTime(p.ThoiGianGD)}
                            </td>
                            <td className="px-3 py-2 text-right font-medium">
                              {formatVND(p.SoTien)}
                            </td>
                            <td className="px-3 py-2">
                              <Badge status={p.TrangThai} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {canManage && conLai > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-stone-200">
                  <form
                    onSubmit={handlePayment}
                    className="rounded-xl border border-stone-200 p-4 space-y-3 bg-stone-50/70"
                  >
                    <div className="flex items-center gap-1.5 text-sm font-semibold text-stone-800">
                      <CreditCard className="w-4 h-4 text-amber-600" />
                      Ghi nhận thanh toán
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <select
                        value={payForm.cong_thanh_toan}
                        onChange={(e) =>
                          setPayForm({ ...payForm, cong_thanh_toan: e.target.value })
                        }
                        className="rounded-lg border border-stone-300 bg-white px-2.5 py-2 text-sm"
                      >
                        <option value="VNPAY">VNPAY</option>
                        <option value="MOMO">MOMO</option>
                        <option value="TIEN_MAT">TIEN_MAT</option>
                        <option value="CHUYEN_KHOAN">CHUYEN_KHOAN</option>
                        <option value="THE_TIN_DUNG">THE_TIN_DUNG</option>
                      </select>
                      <input
                        required
                        type="number"
                        min="1000"
                        step="1000"
                        value={payForm.so_tien}
                        onChange={(e) => setPayForm({ ...payForm, so_tien: e.target.value })}
                        placeholder="Số tiền"
                        className="rounded-lg border border-stone-300 bg-white px-2.5 py-2 text-sm"
                      />
                    </div>
                    <input
                      value={payForm.noi_dung}
                      onChange={(e) => setPayForm({ ...payForm, noi_dung: e.target.value })}
                      placeholder="Nội dung thanh toán"
                      className="w-full rounded-lg border border-stone-300 bg-white px-2.5 py-2 text-sm"
                    />
                    <button
                      disabled={busy}
                      type="submit"
                      className="w-full rounded-lg bg-stone-900 hover:bg-stone-800 text-white py-2 text-sm font-medium cursor-pointer"
                    >
                      Thu tiền ({formatVND(payForm.so_tien || 0)})
                    </button>
                  </form>

                  <form
                    onSubmit={handleApplyVoucher}
                    className="rounded-xl border border-stone-200 p-4 space-y-3 bg-stone-50/70"
                  >
                    <div className="flex items-center gap-1.5 text-sm font-semibold text-stone-800">
                      <Tag className="w-4 h-4 text-amber-600" />
                      Áp mã giảm giá (Voucher)
                    </div>
                    <input
                      required
                      value={voucherCode}
                      onChange={(e) => setVoucherCode(e.target.value)}
                      placeholder="Nhập mã voucher..."
                      className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                    />
                    <button
                      disabled={busy}
                      type="submit"
                      className="w-full rounded-lg bg-amber-600 hover:bg-amber-700 text-white py-2 text-sm font-medium cursor-pointer"
                    >
                      Kiểm tra &amp; Áp mã
                    </button>
                  </form>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-rose-600">{error || "Không tải được hóa đơn."}</p>
          )}
        </div>
      </div>
      {showQr && (
        <PaymentQrModal
          maHd={maHd}
          canConfirmPayment={canManage}
          onClose={() => setShowQr(false)}
          onPaid={() => {
            loadDetail();
            onUpdated?.();
          }}
        />
      )}
    </div>
  );
}
