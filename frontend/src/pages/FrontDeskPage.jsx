import { useEffect, useMemo, useRef, useState } from "react";
import {
  BedDouble,
  CheckCircle2,
  ConciergeBell,
  LogIn,
  LogOut,
  QrCode,
  Receipt,
  RefreshCw,
  Wrench,
  XCircle,
} from "lucide-react";
import { apiFetch } from "../api/client";
import Badge from "../components/Badge";
import CancelBookingModal from "../components/CancelBookingModal";
import InvoiceModal from "../components/InvoiceModal";
import PaymentQrModal from "../components/PaymentQrModal";
import { formatDate, formatVND } from "../utils/format";

const ROOM_STATUSES = ["Trống", "Đang sử dụng", "Đã sẵn sàng", "Bảo trì"];
const BOOKING_STATUSES = [
  "",
  "Chờ xác nhận",
  "Đã xác nhận",
  "Đang lưu trú",
  "Đã trả phòng",
  "Đã hủy",
];

export default function FrontDeskPage({ user }) {
  const [branches, setBranches] = useState([]);
  const [maCn, setMaCn] = useState("");
  const [roomFilter, setRoomFilter] = useState("");
  const [bookingFilter, setBookingFilter] = useState("");
  const [searchQ, setSearchQ] = useState("");
  const [cancelTargetDp, setCancelTargetDp] = useState(null);

  const [rooms, setRooms] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [branchServices, setBranchServices] = useState([]);
  const [loading, setLoading] = useState(false);

  const [serviceTarget, setServiceTarget] = useState(null);
  const [serviceForm, setServiceForm] = useState({ ma_dv: "", so_luong: 1 });
  const [selectedHd, setSelectedHd] = useState(null);
  const [paymentQrHd, setPaymentQrHd] = useState(null);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const requestSeqRef = useRef(0);

  const perms = user?.permissions || [];
  const canReadRooms = Boolean(user?.is_admin) || perms.includes("ROOM.READ_BRANCH");
  const canReadBookings = Boolean(user?.is_admin) || perms.includes("BOOKING.READ_BRANCH");
  const canAccessFrontDesk = canReadRooms || canReadBookings;
  const canManageRoom = perms.includes("ROOM.MANAGE_BRANCH");
  const canConfirm = perms.includes("BOOKING.CONFIRM");
  const canCheckInOut = perms.includes("BOOKING.CHECKIN_OUT");
  const canRecordService = perms.includes("SERVICE.RECORD_USE");
  const canManageInvoice = perms.includes("INVOICE.MANAGE");

  const allowedBranches = useMemo(() => {
    if (!user) return [];
    if (user.is_admin || !user.branch_ids?.length) return branches;
    return branches.filter((b) => user.branch_ids.includes(b.MaCN));
  }, [branches, user]);

  useEffect(() => {
    if (!user || !canAccessFrontDesk) return;
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
  }, [user, canAccessFrontDesk]);

  async function loadOperationalData(branchId = maCn) {
    if (!user || !branchId || !canAccessFrontDesk) return;
    const reqId = ++requestSeqRef.current;
    setLoading(true);
    setError("");
    try {
      const qsRoom = new URLSearchParams({ ma_cn: branchId });
      if (roomFilter) qsRoom.set("trang_thai", roomFilter);

      const qsBooking = new URLSearchParams({ ma_cn: branchId, limit: "100" });
      if (bookingFilter) qsBooking.set("trang_thai", bookingFilter);
      if (searchQ.trim()) qsBooking.set("q", searchQ.trim());

      const [rData, bData, sData] = await Promise.all([
        canReadRooms ? apiFetch(`/api/operations/rooms?${qsRoom}`) : Promise.resolve([]),
        canReadBookings ? apiFetch(`/api/bookings?${qsBooking}`) : Promise.resolve([]),
        apiFetch(`/api/catalog/services?ma_cn=${branchId}`).catch(() => []),
      ]);
      if (reqId !== requestSeqRef.current) return;
      setRooms(rData);
      setBookings(bData);
      setBranchServices(sData);
      setServiceForm((prev) => ({
        ...prev,
        ma_dv: sData.some((s) => String(s.MaDV) === prev.ma_dv)
          ? prev.ma_dv
          : sData.length > 0
          ? String(sData[0].MaDV)
          : "",
      }));
    } catch (err) {
      if (reqId === requestSeqRef.current) {
        setError(err.message);
      }
    } finally {
      if (reqId === requestSeqRef.current) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    loadOperationalData();
  }, [maCn, roomFilter, bookingFilter, searchQ, user]);

  async function handleRoomStatusChange(maPhong, newStatus) {
    setError("");
    setNotice("");
    try {
      await apiFetch(`/api/operations/rooms/${maPhong}/status`, {
        method: "PATCH",
        body: JSON.stringify({ trang_thai: newStatus }),
      });
      setNotice(`Đã cập nhật trạng thái phòng #${maPhong} → "${newStatus}".`);
      await loadOperationalData();
    } catch (err) {
      setError(err.message);
    }
  }

  async function runBookingAction(maDp, action, cancelReason, otpCode) {
    setError("");
    setNotice("");
    try {
      const options = { method: "POST" };
      if (action === "cancel") {
        options.body = JSON.stringify({
          ly_do: cancelReason || "Hủy tại quầy lễ tân",
          otp_code: otpCode || null,
        });
      }
      const res = await apiFetch(`/api/bookings/${maDp}/${action}`, options);
      setNotice(res.message || `Thao tác ${action} thành công cho đơn #${maDp}.`);
      await loadOperationalData();
    } catch (err) {
      setError(err.message);
      if (action === "cancel") {
        throw err;
      }
    }
  }

  async function handleAddService(e) {
    e.preventDefault();
    if (!serviceTarget) return;
    setError("");
    setNotice("");
    try {
      const res = await apiFetch("/api/operations/service-orders", {
        method: "POST",
        body: JSON.stringify({
          ma_dp: serviceTarget.MaDP,
          ma_cn: Number(maCn),
          ma_dv: Number(serviceForm.ma_dv),
          so_luong: Number(serviceForm.so_luong),
        }),
      });
      setNotice(res.message || `Đã gửi yêu cầu dịch vụ cho đơn #${serviceTarget.MaDP}.`);
      setServiceTarget(null);
      await loadOperationalData();
    } catch (err) {
      setError(err.message);
    }
  }

  const roomsByFloor = useMemo(() => {
    const groups = {};
    for (const r of rooms) {
      const floor = `Tầng ${r.Tang}`;
      if (!groups[floor]) groups[floor] = [];
      groups[floor].push(r);
    }
    return Object.entries(groups).sort((a, b) => a[0].localeCompare(b[0], "vi", { numeric: true }));
  }, [rooms]);

  const roomCounts = useMemo(() => {
    const counts = { total: rooms.length };
    for (const st of ROOM_STATUSES) counts[st] = 0;
    for (const r of rooms) counts[r.TrangThai] = (counts[r.TrangThai] || 0) + 1;
    return counts;
  }, [rooms]);

  if (!canAccessFrontDesk) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
        Tài khoản hiện tại không có quyền truy cập Bàn Lễ tân. Vui lòng đăng nhập bằng tài khoản{" "}
        <strong>letan_cn1</strong>, <strong>quanly_cn1</strong> hoặc <strong>admin_hethong</strong>.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="rounded-2xl border border-stone-200 bg-white p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
            <BedDouble className="w-5 h-5 text-amber-600" />
            Bàn Lễ tân & Vận hành phòng
          </h1>
          <p className="text-xs text-stone-500 mt-0.5">
            Theo dõi sơ đồ phòng theo tầng, xác nhận đặt phòng, Check-in/Check-out và ghi nhận dịch vụ phát sinh.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={maCn}
            onChange={(e) => setMaCn(e.target.value)}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
          >
            {allowedBranches.map((b) => (
              <option key={b.MaCN} value={b.MaCN}>
                CN #{b.MaCN} — {b.TenCN}
              </option>
            ))}
          </select>

          <button
            onClick={() => loadOperationalData()}
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

      {/* Room Status Summary & Grid */}
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="font-semibold text-stone-700 mr-1">
              Sơ đồ phòng ({roomCounts.total}):
            </span>
            {ROOM_STATUSES.map((st) => (
              <button
                key={st}
                onClick={() => setRoomFilter((prev) => (prev === st ? "" : st))}
                className={`px-2.5 py-1 rounded-full border transition-colors ${
                  roomFilter === st
                    ? "bg-stone-900 text-white border-stone-900"
                    : "bg-stone-50 text-stone-700 border-stone-200 hover:bg-stone-100"
                }`}
              >
                {st}: {roomCounts[st] || 0}
              </button>
            ))}
            {roomFilter && (
              <button
                onClick={() => setRoomFilter("")}
                className="text-amber-700 hover:underline ml-1"
              >
                Hiện tất cả
              </button>
            )}
          </div>
        </div>

        <div className="space-y-4">
          {roomsByFloor.map(([floor, list]) => (
            <div key={floor} className="space-y-2">
              <p className="text-xs font-bold uppercase tracking-wider text-stone-500">{floor}</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {list.map((r) => (
                  <div
                    key={r.MaPhong}
                    className="rounded-xl border border-stone-200 p-3 bg-stone-50/70 space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-stone-900">P.{r.SoPhong}</span>
                      <Badge status={r.TrangThai} />
                    </div>
                    <p className="text-xs text-stone-600 truncate" title={r.TenLP}>
                      {r.TenLP}
                    </p>
                    {canManageRoom && (
                      <select
                        value={r.TrangThai}
                        onChange={(e) => handleRoomStatusChange(r.MaPhong, e.target.value)}
                        className="w-full rounded-md border border-stone-300 bg-white px-2 py-1 text-[11px]"
                      >
                        {ROOM_STATUSES.map((st) => (
                          <option key={st} value={st}>
                            {st}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Booking Management Table */}
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 className="text-lg font-bold text-stone-900">
            Danh sách đặt phòng chi nhánh ({bookings.length})
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="search"
              placeholder="Tìm tên, SĐT, số phòng, #MaDP..."
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm bg-white w-56"
            />
            <select
              value={bookingFilter}
              onChange={(e) => setBookingFilter(e.target.value)}
              className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm bg-white"
            >
              <option value="">Tất cả trạng thái</option>
              {BOOKING_STATUSES.filter(Boolean).map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left border-collapse">
            <thead>
              <tr className="border-b border-stone-200 text-xs text-stone-500 uppercase bg-stone-50">
                <th className="py-2.5 px-3">Mã ĐP</th>
                <th className="py-2.5 px-3">Khách hàng</th>
                <th className="py-2.5 px-3">Phòng</th>
                <th className="py-2.5 px-3">Check-in / Out</th>
                <th className="py-2.5 px-3">Trạng thái</th>
                <th className="py-2.5 px-3 text-right">Hóa đơn</th>
                <th className="py-2.5 px-3 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {bookings.map((b) => (
                <tr key={b.MaDP} className="hover:bg-stone-50">
                  <td className="py-3 px-3 font-mono font-bold text-stone-900">#{b.MaDP}</td>
                  <td className="py-3 px-3">
                    <p className="font-medium text-stone-900">{b.TenKhachHang}</p>
                    <p className="text-xs text-stone-500">{b.SdtKhachHang}</p>
                  </td>
                  <td className="py-3 px-3">
                    <p className="font-medium">P.{b.SoPhong}</p>
                    <p className="text-xs text-stone-500">{b.TenLP}</p>
                  </td>
                  <td className="py-3 px-3 text-xs">
                    <p>
                      {formatDate(b.NgayCheckIn)} → {formatDate(b.NgayCheckOut)}
                    </p>
                    <p className="text-stone-500">{b.SoDem} đêm</p>
                  </td>
                  <td className="py-3 px-3">
                    <Badge status={b.TrangThaiDatPhong} />
                  </td>
                  <td className="py-3 px-3 text-right">
                    <p className="font-semibold text-stone-900">
                      {formatVND(b.TongTienHoaDon)}
                    </p>
                    {b.TrangThaiHoaDon && (
                      <p className="text-[11px] text-stone-500">{b.TrangThaiHoaDon}</p>
                    )}
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex flex-wrap justify-end gap-1.5">
                      {b.TrangThaiDatPhong === "Chờ xác nhận" && canConfirm && (
                        <button
                          onClick={() => runBookingAction(b.MaDP, "confirm")}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-sky-600 hover:bg-sky-700 text-white text-xs font-medium"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" /> Xác nhận
                        </button>
                      )}
                      {b.TrangThaiDatPhong === "Đã xác nhận" && canCheckInOut && (
                        <button
                          onClick={() => runBookingAction(b.MaDP, "check-in")}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium"
                        >
                          <LogIn className="w-3.5 h-3.5" /> Check-in
                        </button>
                      )}
                      {b.TrangThaiDatPhong === "Đang lưu trú" && canCheckInOut && (
                        <button
                          onClick={() => runBookingAction(b.MaDP, "check-out")}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium"
                        >
                          <LogOut className="w-3.5 h-3.5" /> Check-out
                        </button>
                      )}
                      {b.TrangThaiDatPhong === "Đang lưu trú" && canRecordService && (
                        <button
                          onClick={() => {
                            setServiceTarget(b);
                            if (branchServices.length > 0) {
                              setServiceForm({
                                ma_dv: String(branchServices[0].MaDV),
                                so_luong: 1,
                              });
                            }
                          }}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-stone-300 bg-white hover:bg-stone-100 text-xs font-medium text-stone-800"
                        >
                          <ConciergeBell className="w-3.5 h-3.5 text-amber-600" /> + Dịch vụ
                        </button>
                      )}
                      {b.MaHD && b.TrangThaiHoaDon !== "Đã thanh toán" && b.TrangThaiDatPhong !== "Đã hủy" && (
                        <button
                          onClick={() => setPaymentQrHd(b.MaHD)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-amber-300 bg-amber-50 hover:bg-amber-100 text-xs font-semibold text-amber-800"
                        >
                          <QrCode className="w-3.5 h-3.5" /> QR CK
                        </button>
                      )}
                      {b.MaHD && (
                        <button
                          onClick={() => setSelectedHd(b.MaHD)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-stone-300 bg-white hover:bg-stone-100 text-xs font-medium text-stone-800"
                        >
                          <Receipt className="w-3.5 h-3.5 text-amber-600" /> HĐ #{b.MaHD}
                        </button>
                      )}
                      {["Chờ xác nhận", "Đã xác nhận"].includes(b.TrangThaiDatPhong) &&
                        canConfirm && (
                          <button
                            onClick={() => setCancelTargetDp(b.MaDP)}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-rose-200 bg-rose-50 hover:bg-rose-100 text-xs text-rose-700"
                          >
                            <XCircle className="w-3.5 h-3.5" /> Hủy
                          </button>
                        )}
                    </div>
                  </td>
                </tr>
              ))}
              {bookings.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-stone-400">
                    Không có đơn đặt phòng phù hợp.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Add Service Modal */}
      {serviceTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4 backdrop-blur-xs">
          <form
            onSubmit={handleAddService}
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl border border-stone-200 space-y-4"
          >
            <h3 className="font-bold text-stone-900 flex items-center gap-2">
              <Wrench className="w-4 h-4 text-amber-600" />
              Ghi nhận dịch vụ cho ĐP #{serviceTarget.MaDP} (P.{serviceTarget.SoPhong})
            </h3>

            <label className="block text-xs font-medium text-stone-700">
              Chọn dịch vụ chi nhánh
              <select
                required
                value={serviceForm.ma_dv}
                onChange={(e) => setServiceForm({ ...serviceForm, ma_dv: e.target.value })}
                className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
              >
                {branchServices.map((s) => (
                  <option key={s.MaDV} value={s.MaDV}>
                    {s.TenDV} ({s.LoaiDV}) — {formatVND(s.DonGia)}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-xs font-medium text-stone-700">
              Số lượng
              <input
                type="number"
                min="1"
                required
                value={serviceForm.so_luong}
                onChange={(e) =>
                  setServiceForm({ ...serviceForm, so_luong: Number(e.target.value) })
                }
                className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </label>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setServiceTarget(null)}
                className="px-4 py-2 rounded-lg border border-stone-300 text-sm text-stone-700"
              >
                Đóng
              </button>
              <button
                type="submit"
                className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold"
              >
                Ghi nhận vào hóa đơn
              </button>
            </div>
          </form>
        </div>
      )}

      <InvoiceModal
        maHd={selectedHd}
        canManage={canManageInvoice}
        onClose={() => setSelectedHd(null)}
        onUpdated={() => loadOperationalData()}
      />

      <CancelBookingModal
        maDp={cancelTargetDp}
        requireOtp
        onClose={() => setCancelTargetDp(null)}
        onConfirm={(maDp, reason, otpCode) => runBookingAction(maDp, "cancel", reason, otpCode)}
      />

      <PaymentQrModal
        maHd={paymentQrHd}
        canConfirmPayment={canManageInvoice}
        onClose={() => setPaymentQrHd(null)}
        onPaid={() => loadOperationalData()}
      />
    </div>
  );
}
