import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Compass,
  ConciergeBell,
  Pencil,
  PlusCircle,
  QrCode,
  RefreshCw,
  ScanLine,
  Ticket,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { apiFetch } from "../api/client";
import Badge from "../components/Badge";
import PaymentQrModal from "../components/PaymentQrModal";
import { formatDate, formatDateTime, formatVND } from "../utils/format";

export default function TicketScannerPage({ user, onRequireLogin }) {
  const [branches, setBranches] = useState([]);
  const [maCn, setMaCn] = useState("");
  const [qrInput, setQrInput] = useState("");

  const [zones, setZones] = useState([]);
  const [services, setServices] = useState([]);
  const [ticketTypes, setTicketTypes] = useState([]);
  const [vouchers, setVouchers] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [branchBookings, setBranchBookings] = useState([]);

  const [issueForm, setIssueForm] = useState({
    ma_dp: "",
    ma_loai_ve: "",
    ngay_su_dung: new Date().toISOString().slice(0, 10),
    so_luong: 1,
    voucher_code: "",
  });
  const [issuing, setIssuing] = useState(false);

  const [serviceForm, setServiceForm] = useState({
    ma_dp: "",
    ma_dv: "",
    so_luong: 1,
    ghi_chu: "",
  });
  const [orderingService, setOrderingService] = useState(false);
  const [paymentQrState, setPaymentQrState] = useState({ maHd: null, initialQr: null });

  const [editingSvc, setEditingSvc] = useState(null);
  const [previewQr, setPreviewQr] = useState("");

  const [loading, setLoading] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const perms = user?.permissions || [];
  const canScan = perms.includes("SERVICE.RECORD_USE");
  const canManageService = user?.is_admin || perms.includes("SERVICE.MANAGE_BRANCH");
  const isCustomerUser = Boolean(user?.MaKH && !user?.is_admin);

  const allowedBranches = useMemo(() => {
    if (!user || user.is_admin || !user.branch_ids?.length) return branches;
    return branches.filter((b) => user.branch_ids.includes(b.MaCN));
  }, [branches, user]);

  useEffect(() => {
    apiFetch("/api/catalog/branches")
      .then((all) => {
        setBranches(all);
        if (user && !user.is_admin && user.branch_ids?.length) {
          setMaCn(String(user.branch_ids[0]));
        } else if (all.length > 0) {
          setMaCn(String(all[0].MaCN));
        }
      })
      .catch((err) => setError(err.message));
  }, [user]);

  async function loadData(branchId = maCn) {
    if (!branchId) return;
    setLoading(true);
    setError("");
    try {
      const [zData, sData, ttData, vData] = await Promise.all([
        apiFetch(`/api/catalog/amusement-zones?ma_cn=${branchId}`),
        apiFetch(`/api/catalog/services?ma_cn=${branchId}`),
        apiFetch(`/api/catalog/ticket-types?ma_cn=${branchId}`),
        apiFetch("/api/catalog/vouchers").catch(() => []),
      ]);
      setZones(zData);
      setServices(sData);
      setTicketTypes(ttData);
      setVouchers(vData || []);
      if (ttData.length > 0) {
        setIssueForm((prev) => ({ ...prev, ma_loai_ve: prev.ma_loai_ve || String(ttData[0].MaLoaiVe) }));
      }
      if (sData.length > 0) {
        const firstActive = sData.find((s) => s.TrangThai === "Đang cung cấp") || sData[0];
        setServiceForm((prev) => ({ ...prev, ma_dv: prev.ma_dv || String(firstActive.MaDV) }));
      }

      if (user) {
        const [tData, bData] = await Promise.all([
          apiFetch(`/api/operations/tickets?ma_cn=${branchId}`),
          apiFetch(`/api/bookings?ma_cn=${branchId}&limit=50`).catch(() => []),
        ]);
        setTickets(tData);
        const activeBookings = bData.filter((b) =>
          ["Chờ xác nhận", "Đã xác nhận", "Đang lưu trú"].includes(b.TrangThaiDatPhong)
        );
        setBranchBookings(activeBookings);
        if (activeBookings.length > 0) {
          setIssueForm((prev) => ({
            ...prev,
            ma_dp: prev.ma_dp || String(activeBookings[0].MaDP),
          }));
          setServiceForm((prev) => ({
            ...prev,
            ma_dp: prev.ma_dp || String(activeBookings[0].MaDP),
          }));
        }
      } else {
        setTickets([]);
        setBranchBookings([]);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [maCn, user]);

  async function handleScan(e) {
    e.preventDefault();
    if (!qrInput.trim()) return;
    if (!user) {
      onRequireLogin();
      return;
    }
    setError("");
    setNotice("");
    setScanResult(null);
    try {
      const res = await apiFetch("/api/operations/tickets/scan", {
        method: "POST",
        body: JSON.stringify({
          ma_qr: qrInput.trim(),
          ma_cn: Number(maCn),
        }),
      });
      setScanResult(res);
      setQrInput("");
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleIssueTicket(e) {
    e.preventDefault();
    if (!user) {
      onRequireLogin();
      return;
    }
    if (!issueForm.ma_dp || !issueForm.ma_loai_ve) return;
    setIssuing(true);
    setError("");
    setNotice("");
    try {
      const res = await apiFetch("/api/operations/tickets", {
        method: "POST",
        body: JSON.stringify({
          ma_dp: Number(issueForm.ma_dp),
          ma_loai_ve: Number(issueForm.ma_loai_ve),
          ngay_su_dung: issueForm.ngay_su_dung,
          so_luong: Number(issueForm.so_luong),
          voucher_code: issueForm.voucher_code || undefined,
        }),
      });
      const firstQr = res.tickets?.[0]?.MaQR || "";
      setNotice(`${res.message}${firstQr ? ` (${firstQr})` : ""} — Đã cộng vào hóa đơn!`);
      if (firstQr) {
        setQrInput(firstQr);
        setPreviewQr(firstQr);
      }
      if (isCustomerUser && res.MaHD) {
        setPaymentQrState({ maHd: res.MaHD, initialQr: res.payment_qr || null });
      }
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setIssuing(false);
    }
  }

  async function handleOrderService(e) {
    e.preventDefault();
    if (!user) {
      onRequireLogin();
      return;
    }
    if (!serviceForm.ma_dp || !serviceForm.ma_dv) return;
    setOrderingService(true);
    setError("");
    setNotice("");
    try {
      const res = await apiFetch("/api/operations/service-orders", {
        method: "POST",
        body: JSON.stringify({
          ma_dp: Number(serviceForm.ma_dp),
          ma_cn: Number(maCn),
          ma_dv: Number(serviceForm.ma_dv),
          so_luong: Number(serviceForm.so_luong) || 1,
          ghi_chu: serviceForm.ghi_chu || undefined,
        }),
      });
      setNotice(res.message);
      setServiceForm((prev) => ({ ...prev, so_luong: 1, ghi_chu: "" }));
      if (res.mode === "direct_customer" && res.MaHD) {
        setPaymentQrState({ maHd: res.MaHD, initialQr: res.payment_qr || null });
      }
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setOrderingService(false);
    }
  }

  async function handleSaveService(e) {
    e.preventDefault();
    if (!editingSvc) return;
    setError("");
    setNotice("");
    try {
      await apiFetch(`/api/operations/services/${editingSvc.MaCN}/${editingSvc.MaDV}`, {
        method: "PATCH",
        body: JSON.stringify({
          don_gia: Number(editingSvc.DonGia),
          trang_thai: editingSvc.TrangThai,
        }),
      });
      setNotice(`Đã cập nhật dịch vụ "${editingSvc.TenDV}" tại chi nhánh.`);
      setEditingSvc(null);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header & Branch Filter */}
      <div className="rounded-2xl border border-stone-200 bg-white p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
            <QrCode className="w-5 h-5 text-amber-600" />
            Cổng Soát Vé QR &amp; Dịch vụ Chi nhánh
          </h1>
          <p className="text-xs text-stone-500 mt-0.5">
            Phát hành vé điện tử mới kèm mã QR và kiểm tra vé qua{" "}
            <code className="text-stone-700 bg-stone-100 px-1 py-0.5 rounded-sm">
              sp_quet_ve_dien_tu
            </code>
            .
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={maCn}
            onChange={(e) => {
              setMaCn(e.target.value);
              setIssueForm((prev) => ({ ...prev, ma_dp: "", ma_loai_ve: "" }));
              setServiceForm((prev) => ({ ...prev, ma_dp: "", ma_dv: "" }));
            }}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
          >
            {allowedBranches.map((b) => (
              <option key={b.MaCN} value={b.MaCN}>
                CN #{b.MaCN} — {b.TenCN}
              </option>
            ))}
          </select>
          <button
            onClick={() => loadData()}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 bg-stone-50 hover:bg-stone-100 px-3 py-2 text-sm font-medium text-stone-700"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Làm mới
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {notice && (
        <div className="rounded-xl bg-emerald-50 border border-emerald-200 px-4 py-3 text-sm text-emerald-700">
          {notice}
        </div>
      )}

      {/* Scanner Box + Amusement Zones */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Scan Card */}
          <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
            <h2 className="font-bold text-stone-900 flex items-center gap-2">
              <ScanLine className="w-5 h-5 text-amber-600" />
              Quét / Kiểm tra mã QR vé điện tử
            </h2>

            <form onSubmit={handleScan} className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                required
                placeholder="Nhập hoặc chọn nhanh mã QR (vd: QR-LIVE-...)..."
                value={qrInput}
                onChange={(e) => setQrInput(e.target.value)}
                className="flex-1 rounded-lg border border-stone-300 px-3.5 py-2.5 text-sm font-mono"
              />
              <button
                type="submit"
                disabled={user && !canScan}
                className="rounded-lg bg-stone-900 hover:bg-stone-800 text-white font-semibold text-sm px-5 py-2.5 disabled:opacity-50"
              >
                Soát vé ngay
              </button>
            </form>

            {user && !canScan && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Tài khoản hiện tại chỉ có quyền xem. Đăng nhập bằng{" "}
                <strong>dichvu_cn2</strong>, <strong>letan_cn1</strong>,{" "}
                <strong>quanly_cn1</strong> hoặc <strong>admin_hethong</strong> để soát/phát hành vé.
              </p>
            )}

            {error && (
              <div className="rounded-xl bg-rose-50 border border-rose-200 px-4 py-3 text-sm text-rose-700">
                {error}
              </div>
            )}

            {scanResult && (
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-4 text-sm text-emerald-900 flex items-center gap-4">
                {scanResult.ticket?.MaQR && (
                  <div className="bg-white p-1.5 rounded-lg border border-emerald-200 shrink-0">
                    <QRCodeSVG value={scanResult.ticket.MaQR} size={64} />
                  </div>
                )}
                <div className="space-y-1">
                  <p className="font-bold flex items-center gap-1.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    {scanResult.message}
                  </p>
                  {scanResult.ticket && (
                    <p className="text-xs text-emerald-800">
                      Mã QR: <span className="font-mono font-semibold">{scanResult.ticket.MaQR}</span>{" "}
                      · Khách: {scanResult.ticket.TenKhachHang} · {scanResult.ticket.TenLoaiVe} ·{" "}
                      {scanResult.ticket.TenKhu}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Issue / Buy Ticket Card (All logged-in roles) */}
          {ticketTypes.length > 0 && (
            <form
              onSubmit={handleIssueTicket}
              className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-bold text-stone-900 flex items-center gap-2 text-base">
                  <PlusCircle className="w-5 h-5 text-amber-600" />
                  {isCustomerUser
                    ? "Đặt mua vé QR khu vui chơi (gắn đơn đặt phòng)"
                    : "Phát hành vé QR mới cho khách (gắn hóa đơn đặt phòng)"}
                </h2>
                {!user && (
                  <button
                    type="button"
                    onClick={onRequireLogin}
                    className="text-xs font-semibold text-amber-700 hover:underline"
                  >
                    Đăng nhập để đặt vé →
                  </button>
                )}
              </div>

              {!user ? (
                <p className="text-xs text-stone-500">
                  Vui lòng đăng nhập để chọn đơn đặt phòng và mua vé QR trực tuyến.
                </p>
              ) : branchBookings.length === 0 ? (
                <p className="text-xs text-stone-500">
                  {isCustomerUser
                    ? "Bạn chưa có đơn đặt phòng đang hoạt động tại chi nhánh này."
                    : "Chi nhánh hiện chưa có đơn đặt phòng ở trạng thái Chờ xác nhận / Đã xác nhận / Đang lưu trú."}
                </p>
              ) : (
                <div className="space-y-3 text-xs">
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    <label className="block font-medium text-stone-700">
                      Đơn đặt phòng
                      <select
                        required
                        value={issueForm.ma_dp}
                        onChange={(e) => setIssueForm({ ...issueForm, ma_dp: e.target.value })}
                        className="mt-1 w-full rounded-lg border border-stone-300 px-2.5 py-2 text-xs bg-white"
                      >
                        {branchBookings.map((b) => (
                          <option key={b.MaDP} value={b.MaDP}>
                            #{b.MaDP} — P.{b.SoPhong} ({b.TenKhachHang})
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="block font-medium text-stone-700">
                      Loại vé vui chơi
                      <select
                        required
                        value={issueForm.ma_loai_ve}
                        onChange={(e) => setIssueForm({ ...issueForm, ma_loai_ve: e.target.value })}
                        className="mt-1 w-full rounded-lg border border-stone-300 px-2.5 py-2 text-xs bg-white"
                      >
                        {ticketTypes.map((t) => (
                          <option key={t.MaLoaiVe} value={t.MaLoaiVe}>
                            {t.TenLoaiVe} ({t.DoiTuong}) — {formatVND(t.GiaVe)}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="block font-medium text-stone-700">
                      Ngày sử dụng
                      <input
                        type="date"
                        required
                        value={issueForm.ngay_su_dung}
                        onChange={(e) => setIssueForm({ ...issueForm, ngay_su_dung: e.target.value })}
                        className="mt-1 w-full rounded-lg border border-stone-300 px-2.5 py-2 text-xs"
                      />
                    </label>

                    <div className="flex items-end gap-2">
                      <label className="block font-medium text-stone-700 w-20">
                        SL
                        <input
                          type="number"
                          min="1"
                          max="20"
                          value={issueForm.so_luong}
                          onChange={(e) =>
                            setIssueForm({ ...issueForm, so_luong: Number(e.target.value) })
                          }
                          className="mt-1 w-full rounded-lg border border-stone-300 px-2.5 py-2 text-xs"
                        />
                      </label>
                      <button
                        type="submit"
                        disabled={issuing}
                        className="flex-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold py-2 px-3 disabled:opacity-50"
                      >
                        {issuing ? "Đang tạo..." : isCustomerUser ? "Đặt vé & Quét QR" : "Phát hành QR"}
                      </button>
                    </div>
                  </div>

                  {vouchers.some((v) => v.TrangThai === "Hiệu lực" && v.LoaiApDung === "Khu vui chơi") && (
                    <label className="block font-medium text-stone-700 max-w-sm">
                      Voucher Khu vui chơi (tối đa 1 mã — tùy chọn)
                      <select
                        value={issueForm.voucher_code}
                        onChange={(e) => setIssueForm({ ...issueForm, voucher_code: e.target.value })}
                        className="mt-1 w-full rounded-lg border border-stone-300 px-2.5 py-2 text-xs bg-white"
                      >
                        <option value="">Không dùng voucher</option>
                        {vouchers
                          .filter((v) => v.TrangThai === "Hiệu lực" && v.LoaiApDung === "Khu vui chơi")
                          .map((v) => (
                            <option key={v.MaVoucher} value={v.Code}>
                              {v.Code} —{" "}
                              {v.LoaiGiam === "Phần trăm"
                                ? `Giảm ${v.GiaTriGiam}% (tối đa ${formatVND(v.GiamToiDa)})`
                                : `Giảm ${formatVND(v.GiaTriGiam)}`}
                            </option>
                          ))}
                      </select>
                    </label>
                  )}
                </div>
              )}
            </form>
          )}

          {/* Service Ordering Card (All logged-in roles) */}
          {services.length > 0 && (
            <form
              id="service-order-form"
              onSubmit={handleOrderService}
              className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-bold text-stone-900 flex items-center gap-2 text-base">
                  <ConciergeBell className="w-5 h-5 text-emerald-600" />
                  {isCustomerUser
                    ? "Đặt thêm dịch vụ (Thanh toán QR ngay)"
                    : "Đặt / Đề xuất dịch vụ chi nhánh (gửi thông báo khách xác nhận)"}
                </h2>
                {!user && (
                  <button
                    type="button"
                    onClick={onRequireLogin}
                    className="text-xs font-semibold text-emerald-700 hover:underline"
                  >
                    Đăng nhập để đặt dịch vụ →
                  </button>
                )}
              </div>

              {user && (
                <p className="text-[11px] rounded-lg px-3 py-2 border border-stone-200 bg-stone-50 text-stone-700">
                  {isCustomerUser
                    ? "Bạn đang đặt với tư cách Khách hàng: dịch vụ được ghi nhận trực tiếp vào hóa đơn đơn đã chọn và mở ngay mã VietQR thanh toán."
                    : "Bạn đang đặt với vai trò Nhân viên/Quản trị: yêu cầu sẽ gửi thông báo về tài khoản khách hàng; chỉ ghi nhận vào hóa đơn khi khách bấm Xác nhận."}
                </p>
              )}

              {!user ? (
                <p className="text-xs text-stone-500">
                  Vui lòng đăng nhập để chọn đơn đặt phòng và đặt dịch vụ trực tuyến.
                </p>
              ) : branchBookings.length === 0 ? (
                <p className="text-xs text-stone-500">
                  Chưa có đơn đặt phòng hoạt động tại chi nhánh này để gắn dịch vụ.
                </p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
                  <label className="block font-medium text-stone-700">
                    Đơn đặt phòng
                    <select
                      required
                      value={serviceForm.ma_dp}
                      onChange={(e) => setServiceForm({ ...serviceForm, ma_dp: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-stone-300 px-2.5 py-2 text-xs bg-white"
                    >
                      {branchBookings.map((b) => (
                        <option key={b.MaDP} value={b.MaDP}>
                          #{b.MaDP} — P.{b.SoPhong} ({b.TenKhachHang})
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="block font-medium text-stone-700">
                    Dịch vụ
                    <select
                      required
                      value={serviceForm.ma_dv}
                      onChange={(e) => setServiceForm({ ...serviceForm, ma_dv: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-stone-300 px-2.5 py-2 text-xs bg-white"
                    >
                      {services
                        .filter((s) => s.TrangThai !== "Tạm ngưng")
                        .map((s) => (
                          <option key={s.MaDV} value={s.MaDV}>
                            {s.TenDV} — {formatVND(s.DonGia)}
                          </option>
                        ))}
                    </select>
                  </label>

                  <label className="block font-medium text-stone-700">
                    Ghi chú (tùy chọn)
                    <input
                      type="text"
                      placeholder="Khung giờ, yêu cầu riêng..."
                      value={serviceForm.ghi_chu}
                      onChange={(e) => setServiceForm({ ...serviceForm, ghi_chu: e.target.value })}
                      className="mt-1 w-full rounded-lg border border-stone-300 px-2.5 py-2 text-xs"
                    />
                  </label>

                  <div className="flex items-end gap-2">
                    <label className="block font-medium text-stone-700 w-20">
                      SL
                      <input
                        type="number"
                        min="1"
                        max="100"
                        value={serviceForm.so_luong}
                        onChange={(e) =>
                          setServiceForm({ ...serviceForm, so_luong: Number(e.target.value) })
                        }
                        className="mt-1 w-full rounded-lg border border-stone-300 px-2.5 py-2 text-xs"
                      />
                    </label>
                    <button
                      type="submit"
                      disabled={orderingService}
                      className="flex-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-2 px-3 disabled:opacity-50"
                    >
                      {orderingService
                        ? "Đang gửi..."
                        : isCustomerUser
                        ? "Đặt & Thanh toán QR"
                        : "Gửi khách xác nhận"}
                    </button>
                  </div>
                </div>
              )}
            </form>
          )}
        </div>

        {/* Zones */}
        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3 h-fit">
          <h2 className="font-bold text-stone-900 flex items-center gap-2">
            <Compass className="w-5 h-5 text-amber-600" />
            Khu vui chơi tại chi nhánh ({zones.length})
          </h2>
          {zones.length === 0 ? (
            <p className="text-xs text-stone-500">Chi nhánh chưa có khu vui chơi.</p>
          ) : (
            <div className="space-y-2.5">
              {zones.map((z) => (
                <div
                  key={z.MaKhu}
                  className="rounded-xl border border-stone-200 bg-stone-50 p-3 text-xs space-y-1"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-stone-900">{z.TenKhu}</span>
                    <span className="px-2 py-0.5 rounded-full bg-white border border-stone-200 text-stone-600">
                      {z.LoaiKhu}
                    </span>
                  </div>
                  <p className="text-stone-500">
                    Giờ mở cửa: {String(z.GioMoCua || "").slice(0, 5)} –{" "}
                    {String(z.GioDongCua || "").slice(0, 5)}
                  </p>
                  {z.MoTa && <p className="text-stone-600">{z.MoTa}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* E-Tickets Table */}
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-stone-900 flex items-center gap-2">
            <Ticket className="w-5 h-5 text-amber-600" />
            Danh sách vé điện tử {user ? `(${tickets.length})` : ""}
          </h2>
          {!user && (
            <button
              onClick={onRequireLogin}
              className="text-xs font-semibold text-amber-700 hover:underline"
            >
              Đăng nhập để xem danh sách vé →
            </button>
          )}
        </div>

        {user && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left border-collapse">
              <thead>
                <tr className="border-b border-stone-200 text-xs text-stone-500 uppercase bg-stone-50">
                  <th className="py-2.5 px-3">Mã QR</th>
                  <th className="py-2.5 px-3">Khu / Loại vé</th>
                  <th className="py-2.5 px-3">Khách hàng</th>
                  <th className="py-2.5 px-3">Ngày sử dụng</th>
                  <th className="py-2.5 px-3">Trạng thái</th>
                  <th className="py-2.5 px-3">Thời gian quét</th>
                  <th className="py-2.5 px-3 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {tickets.map((t) => (
                  <tr key={t.MaVe} className="hover:bg-stone-50">
                    <td className="py-2.5 px-3 font-mono font-semibold text-stone-900">
                      {t.MaQR}
                    </td>
                    <td className="py-2.5 px-3 text-xs">
                      <p className="font-medium text-stone-900">{t.TenLoaiVe}</p>
                      <p className="text-stone-500">
                        {t.TenKhu} · {t.DoiTuong}
                      </p>
                    </td>
                    <td className="py-2.5 px-3 text-xs">{t.TenKhachHang}</td>
                    <td className="py-2.5 px-3 text-xs">{formatDate(t.NgaySuDung)}</td>
                    <td className="py-2.5 px-3">
                      <Badge status={t.TrangThai} />
                    </td>
                    <td className="py-2.5 px-3 text-xs text-stone-500">
                      {t.ThoiGianQuet ? formatDateTime(t.ThoiGianQuet) : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <div className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => setPreviewQr(t.MaQR)}
                          className="px-2 py-1 rounded-md border border-stone-300 bg-white hover:bg-stone-100 text-xs text-stone-700"
                        >
                          Xem QR
                        </button>
                        <button
                          type="button"
                          onClick={() => setQrInput(t.MaQR)}
                          className="px-2.5 py-1 rounded-md border border-stone-300 bg-white hover:bg-stone-100 text-xs font-medium text-stone-800"
                        >
                          Chọn nhanh
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
                {tickets.length === 0 && (
                  <tr>
                    <td colSpan={7} className="py-6 text-center text-stone-400">
                      Chưa có vé điện tử nào tại chi nhánh này.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Branch Services Catalog */}
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3">
        <h2 className="font-bold text-stone-900 flex items-center gap-2">
          <ConciergeBell className="w-5 h-5 text-amber-600" />
          Bảng giá dịch vụ chi nhánh ({services.length})
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {services.map((s) => (
            <div
              key={`${s.MaCN}-${s.MaDV}`}
              className="rounded-xl border border-stone-200 p-3.5 bg-stone-50/70 flex items-start justify-between gap-3 text-sm"
            >
              <div>
                <p className="font-semibold text-stone-900">{s.TenDV}</p>
                <p className="text-xs text-stone-500">{s.LoaiDV}</p>
                {s.MoTa && <p className="text-xs text-stone-600 mt-1">{s.MoTa}</p>}
              </div>
              <div className="text-right shrink-0 space-y-1.5">
                <p className="font-bold text-amber-700">{formatVND(s.DonGia)}</p>
                <div>
                  <Badge status={s.TrangThai} />
                </div>
                <div className="flex items-center justify-end gap-2">
                  {s.TrangThai !== "Tạm ngưng" && (
                    <button
                      type="button"
                      onClick={() => {
                        if (!user) {
                          onRequireLogin();
                          return;
                        }
                        setServiceForm((prev) => ({ ...prev, ma_dv: String(s.MaDV) }));
                        document.getElementById("service-order-form")?.scrollIntoView({ behavior: "smooth" });
                      }}
                      className="px-2 py-0.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-semibold"
                    >
                      {isCustomerUser ? "Đặt ngay" : "Chọn"}
                    </button>
                  )}
                  {canManageService && (
                    <button
                      type="button"
                      onClick={() => setEditingSvc({ ...s })}
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-stone-600 hover:text-stone-900"
                    >
                      <Pencil className="w-3 h-3" /> Sửa giá
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* QR Preview Modal */}
      {previewQr && (
        <div
          onClick={() => setPreviewQr("")}
          className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4 backdrop-blur-xs"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="rounded-2xl bg-white p-6 shadow-2xl border border-stone-200 text-center space-y-3 max-w-xs w-full"
          >
            <p className="font-bold text-stone-900 text-sm">Mã QR Vé điện tử</p>
            <div className="inline-block p-3 bg-white border border-stone-200 rounded-xl">
              <QRCodeSVG value={previewQr} size={168} />
            </div>
            <p className="font-mono text-xs text-stone-700 break-all">{previewQr}</p>
            <button
              onClick={() => setPreviewQr("")}
              className="w-full rounded-lg bg-stone-900 text-white py-2 text-xs font-semibold"
            >
              Đóng
            </button>
          </div>
        </div>
      )}

      {/* Edit Service Modal */}
      {editingSvc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4 backdrop-blur-xs">
          <form
            onSubmit={handleSaveService}
            className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-2xl border border-stone-200 space-y-3"
          >
            <h3 className="font-bold text-stone-900 text-sm">
              Cập nhật dịch vụ: {editingSvc.TenDV}
            </h3>
            <label className="block text-xs font-medium text-stone-700">
              Đơn giá (VND)
              <input
                type="number"
                min="0"
                step="1000"
                required
                value={editingSvc.DonGia}
                onChange={(e) => setEditingSvc({ ...editingSvc, DonGia: e.target.value })}
                className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-xs font-medium text-stone-700">
              Trạng thái phục vụ
              <select
                value={editingSvc.TrangThai}
                onChange={(e) => setEditingSvc({ ...editingSvc, TrangThai: e.target.value })}
                className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
              >
                <option value="Đang cung cấp">Đang cung cấp</option>
                <option value="Còn phục vụ">Còn phục vụ</option>
                <option value="Tạm ngưng">Tạm ngưng</option>
              </select>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setEditingSvc(null)}
                className="px-3 py-1.5 rounded-lg border border-stone-300 text-xs"
              >
                Đóng
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded-lg bg-amber-600 text-white text-xs font-semibold"
              >
                Lưu thay đổi
              </button>
            </div>
          </form>
        </div>
      )}
      <PaymentQrModal
        maHd={paymentQrState.maHd}
        initialQr={paymentQrState.initialQr}
        canConfirmPayment={canScan || user?.permissions?.includes("INVOICE.MANAGE")}
        onClose={() => setPaymentQrState({ maHd: null, initialQr: null })}
        onPaid={() => loadData()}
      />
    </div>
  );
}
