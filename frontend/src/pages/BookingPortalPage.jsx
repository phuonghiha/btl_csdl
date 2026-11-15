import { useEffect, useState } from "react";
import {
  Building2,
  CalendarDays,
  ChevronDown,
  ChevronUp,
  Gift,
  Hotel,
  QrCode,
  Receipt,
  Search,
  Sparkles,
  Tag,
  Ticket,
  UserPlus,
  Users,
  XCircle,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
import { apiFetch } from "../api/client";
import Badge from "../components/Badge";
import CancelBookingModal from "../components/CancelBookingModal";
import InvoiceModal from "../components/InvoiceModal";
import PaymentQrModal from "../components/PaymentQrModal";
import { formatDate, formatDateTime, formatVND } from "../utils/format";

function getNextDay(dateStr) {
  if (!dateStr) return "";
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return "";
  const next = new Date(Date.UTC(y, m - 1, d + 1));
  return next.toISOString().slice(0, 10);
}

export default function BookingPortalPage({ user, onRequireLogin }) {
  const [branches, setBranches] = useState([]);
  const [combos, setCombos] = useState([]);
  const [ticketTypes, setTicketTypes] = useState([]);
  const [vouchers, setVouchers] = useState([]);

  const [maCn, setMaCn] = useState(1);
  const [checkIn, setCheckIn] = useState("2026-12-10");
  const [checkOut, setCheckOut] = useState("2026-12-13");
  const [sucChua, setSucChua] = useState(2);
  const [holidayInfo, setHolidayInfo] = useState({ is_holiday: false, holiday_names: [], holiday_dates: [] });

  const [rooms, setRooms] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  const [bookingRoom, setBookingRoom] = useState(null);
  const [selectedComboId, setSelectedComboId] = useState("");
  const [selectedTicketTypeId, setSelectedTicketTypeId] = useState("");
  const [selectedTicketQty, setSelectedTicketQty] = useState(1);
  const [selectedVoucherCodes, setSelectedVoucherCodes] = useState([]);
  const [maKhInput, setMaKhInput] = useState("");
  const [customerSearch, setCustomerSearch] = useState("");
  const [customerResults, setCustomerResults] = useState([]);
  const [showNewCustomer, setShowNewCustomer] = useState(false);
  const [newCustomer, setNewCustomer] = useState({
    ho_ten: "",
    cccd: "",
    sdt: "",
    email: "",
    dia_chi: "",
  });
  const [ghiChu, setGhiChu] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [myBookings, setMyBookings] = useState([]);
  const [bookingSearchQ, setBookingSearchQ] = useState("");
  const [expandedDp, setExpandedDp] = useState(null);
  const [dpDetailMap, setDpDetailMap] = useState({});
  const [selectedHd, setSelectedHd] = useState(null);
  const [paymentQrState, setPaymentQrState] = useState({ maHd: null, initialQr: null });
  const [cancelTargetDp, setCancelTargetDp] = useState(null);

  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([apiFetch("/api/catalog/branches"), apiFetch("/api/catalog/vouchers")])
      .then(([b, v]) => {
        setBranches(b);
        if (b.length > 0) setMaCn(b[0].MaCN);
        setVouchers(v);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!maCn) return;
    Promise.all([
      apiFetch(`/api/catalog/combos?ma_cn=${maCn}`),
      apiFetch(`/api/catalog/ticket-types?ma_cn=${maCn}`),
    ])
      .then(([c, t]) => {
        setCombos(c || []);
        setTicketTypes(t || []);
      })
      .catch(() => {
        setCombos([]);
        setTicketTypes([]);
      });
    setSelectedTicketTypeId("");
  }, [maCn]);

  useEffect(() => {
    if (!checkIn || !checkOut || checkOut <= checkIn) {
      setHolidayInfo({ is_holiday: false, holiday_names: [], holiday_dates: [] });
      return;
    }
    apiFetch(`/api/bookings/holiday-status?ngay_checkin=${checkIn}&ngay_checkout=${checkOut}`)
      .then((res) => setHolidayInfo(res || { is_holiday: false, holiday_names: [], holiday_dates: [] }))
      .catch(() => setHolidayInfo({ is_holiday: false, holiday_names: [], holiday_dates: [] }));
  }, [checkIn, checkOut]);

  useEffect(() => {
    const hasAmusement = Boolean(selectedTicketTypeId);
    const activeMap = new Map(vouchers.map((v) => [v.Code, v]));
    setSelectedVoucherCodes((prev) => {
      const next = [];
      let ksCount = 0;
      let vcCount = 0;
      for (const code of prev) {
        const v = activeMap.get(code);
        if (!v || v.TrangThai !== "Hiệu lực") continue;
        if (v.LoaiApDung === "Khu vui chơi" && !hasAmusement) continue;
        if (holidayInfo.is_holiday) {
          if (!hasAmusement) continue;
          if (next.length >= 1) continue;
        } else {
          if (v.LoaiApDung === "Khách sạn" && ksCount >= 1) continue;
          if (v.LoaiApDung === "Khu vui chơi" && vcCount >= 1) continue;
          if (next.length >= 2) continue;
        }
        next.push(code);
        if (v.LoaiApDung === "Khách sạn") ksCount += 1;
        else vcCount += 1;
      }
      return next.length === prev.length && next.every((c, idx) => c === prev[idx]) ? prev : next;
    });
  }, [holidayInfo.is_holiday, selectedTicketTypeId, vouchers]);

  async function loadMyBookings(q = bookingSearchQ) {
    if (!user) {
      setMyBookings([]);
      return;
    }
    try {
      const qs = new URLSearchParams({ limit: "30" });
      if (q.trim()) qs.set("q", q.trim());
      const data = await apiFetch(`/api/bookings?${qs}`);
      setMyBookings(data);
    } catch {
      setMyBookings([]);
    }
  }

  useEffect(() => {
    loadMyBookings();
  }, [user, bookingSearchQ]);

  useEffect(() => {
    if (!bookingRoom || !user || user.MaKH) return;
    const timer = setTimeout(() => {
      apiFetch(`/api/operations/customers?q=${encodeURIComponent(customerSearch)}&limit=10`)
        .then(setCustomerResults)
        .catch(() => setCustomerResults([]));
    }, 200);
    return () => clearTimeout(timer);
  }, [bookingRoom, customerSearch, user]);

  function handleCheckInChange(nextCheckIn) {
    setCheckIn(nextCheckIn);
    setCheckOut("");
    setRooms([]);
    setSearched(false);
    setBookingRoom(null);
    setError("");
  }

  function handleCheckOutChange(nextCheckOut) {
    if (nextCheckOut && checkIn && nextCheckOut <= checkIn) {
      setCheckOut("");
      setError("Ngày trả phòng phải sau ngày nhận phòng (các ngày trước hoặc trùng ngày nhận đã bị vô hiệu hóa).");
      return;
    }
    setCheckOut(nextCheckOut);
    setRooms([]);
    setSearched(false);
    setBookingRoom(null);
    setError("");
  }

  async function handleSearch(e) {
    if (e) e.preventDefault();
    if (!checkIn || !checkOut) {
      setError("Vui lòng chọn đầy đủ ngày nhận phòng và ngày trả phòng.");
      return;
    }
    if (checkOut <= checkIn) {
      setError("Ngày trả phòng phải sau ngày nhận phòng.");
      return;
    }
    setSearching(true);
    setError("");
    setNotice("");
    try {
      const data = await apiFetch(
        `/api/bookings/availability?ma_cn=${maCn}&ngay_checkin=${checkIn}&ngay_checkout=${checkOut}&suc_chua=${sucChua}`
      );
      setRooms(data);
      setSearched(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSearching(false);
    }
  }

  async function handleQuickCreateCustomer() {
    setError("");
    try {
      const res = await apiFetch("/api/operations/customers", {
        method: "POST",
        body: JSON.stringify(newCustomer),
      });
      setMaKhInput(String(res.MaKH));
      setCustomerResults((prev) => [{ MaKH: res.MaKH, HoTen: res.HoTen, SDT: res.SDT }, ...prev]);
      setShowNewCustomer(false);
      setNewCustomer({ ho_ten: "", cccd: "", sdt: "", email: "", dia_chi: "" });
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleCreateBooking(e) {
    e.preventDefault();
    if (!bookingRoom) return;
    if (!checkIn || !checkOut || checkOut <= checkIn) {
      setError("Vui lòng chọn ngày nhận phòng và ngày trả phòng hợp lệ.");
      return;
    }
    if (!user) {
      onRequireLogin();
      return;
    }
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      const payload = {
        ma_phong: bookingRoom.MaPhong,
        ngay_checkin: checkIn,
        ngay_checkout: checkOut,
        ma_combo: selectedComboId ? Number(selectedComboId) : undefined,
        ghi_chu: ghiChu || undefined,
        ticket_items: selectedTicketTypeId
          ? [
              {
                ma_loai_ve: Number(selectedTicketTypeId),
                so_luong: Number(selectedTicketQty) || 1,
                ngay_su_dung: checkIn,
              },
            ]
          : [],
        voucher_codes: selectedVoucherCodes,
      };
      if (!user.MaKH) {
        if (!maKhInput.trim()) {
          throw new Error("Vui lòng chọn khách hàng trước khi tạo đơn.");
        }
        payload.ma_kh = Number(maKhInput.trim());
      }
      const res = await apiFetch("/api/bookings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setNotice(
        `Đặt phòng thành công! Mã đặt phòng #${res.MaDP}, Hóa đơn #${res.MaHD} đã được tạo.`
      );
      setBookingRoom(null);
      setSelectedComboId("");
      setSelectedTicketTypeId("");
      setSelectedTicketQty(1);
      setSelectedVoucherCodes([]);
      setGhiChu("");
      if (res.MaHD) {
        setPaymentQrState({ maHd: res.MaHD, initialQr: res.payment_qr || null });
      }
      await Promise.all([handleSearch(), loadMyBookings()]);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancelBooking(maDp, lyDo, otpCode) {
    setError("");
    setNotice("");
    try {
      await apiFetch(`/api/bookings/${maDp}/cancel`, {
        method: "POST",
        body: JSON.stringify({ ly_do: lyDo, otp_code: otpCode || null }),
      });
      setNotice(`Đã hủy đơn đặt phòng #${maDp}.`);
      await loadMyBookings();
      if (searched) await handleSearch();
    } catch (err) {
      setError(err.message);
      throw err;
    }
  }

  async function toggleDetail(maDp) {
    if (expandedDp === maDp) {
      setExpandedDp(null);
      return;
    }
    setExpandedDp(maDp);
    if (!dpDetailMap[maDp]) {
      try {
        const detail = await apiFetch(`/api/bookings/${maDp}`);
        setDpDetailMap((prev) => ({ ...prev, [maDp]: detail }));
      } catch (err) {
        setError(err.message);
      }
    }
  }

  const selectedBranch = branches.find((b) => b.MaCN === Number(maCn));
  const canManageInvoice = user?.permissions?.includes("INVOICE.MANAGE");
  const roomCombos = bookingRoom
    ? combos.filter((c) => c.MaLP === bookingRoom.MaLP)
    : [];

  const activeVouchers = vouchers.filter((v) => v.TrangThai === "Hiệu lực");
  const hasAmusementTicket = Boolean(selectedTicketTypeId);

  function getVoucherDisabledReason(v) {
    const isSelected = selectedVoucherCodes.includes(v.Code);
    if (isSelected) return "";
    if (v.LoaiApDung === "Khu vui chơi" && !hasAmusementTicket) {
      return "Cần chọn thêm vé khu vui chơi để áp dụng voucher Khu vui chơi";
    }
    if (holidayInfo.is_holiday) {
      if (!hasAmusementTicket) {
        return "Ngày lễ chỉ đặt khách sạn không được áp dụng voucher";
      }
      if (selectedVoucherCodes.length >= 1) {
        return "Ngày lễ chỉ được chọn tối đa 1 voucher (Khách sạn hoặc Khu vui chơi)";
      }
      return "";
    }
    const pickedObjects = selectedVoucherCodes
      .map((code) => activeVouchers.find((item) => item.Code === code))
      .filter(Boolean);
    const hasKs = pickedObjects.some((item) => item.LoaiApDung === "Khách sạn");
    const hasVc = pickedObjects.some((item) => item.LoaiApDung === "Khu vui chơi");
    if (v.LoaiApDung === "Khách sạn" && hasKs) {
      return "Đã chọn 1 voucher Khách sạn";
    }
    if (v.LoaiApDung === "Khu vui chơi" && hasVc) {
      return "Đã chọn 1 voucher Khu vui chơi";
    }
    if (selectedVoucherCodes.length >= 2) {
      return "Tối đa 2 voucher (1 Khách sạn + 1 Khu vui chơi)";
    }
    return "";
  }

  function handleToggleVoucher(v) {
    setSelectedVoucherCodes((prev) => {
      if (prev.includes(v.Code)) {
        return prev.filter((c) => c !== v.Code);
      }
      if (getVoucherDisabledReason(v)) return prev;
      return [...prev, v.Code];
    });
  }

  return (
    <div className="space-y-8">
      {/* Hero + Search Box */}
      <section className="rounded-2xl bg-gradient-to-br from-stone-900 via-stone-800 to-amber-950 text-white p-6 md:p-8 shadow-lg">
        <div className="max-w-3xl mb-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 text-xs font-medium mb-3 border border-amber-400/30">
            <Sparkles className="w-3.5 h-3.5" />
            Giá phòng tự động theo Mùa du lịch &amp; Lễ Tết Âm lịch
          </div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">
            Đặt phòng trực tuyến trên 10 chi nhánh
          </h1>
          <p className="text-stone-300 text-sm mt-1.5">
            Tìm phòng trống theo thời gian thực, chọn gói Combo nghỉ dưỡng, xem vé QR điện tử và hóa đơn chi tiết.
          </p>
        </div>

        <form
          onSubmit={handleSearch}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 bg-white text-stone-900 p-4 rounded-xl shadow-md"
        >
          <label className="block text-xs font-medium text-stone-600 lg:col-span-2">
            <span className="flex items-center gap-1 mb-1">
              <Building2 className="w-3.5 h-3.5 text-amber-600" /> Chi nhánh
            </span>
            <select
              value={maCn}
              onChange={(e) => {
                setMaCn(Number(e.target.value));
                setRooms([]);
                setSearched(false);
                setBookingRoom(null);
              }}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
            >
              {branches.map((b) => (
                <option key={b.MaCN} value={b.MaCN}>
                  #{b.MaCN} — {b.TenCN}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs font-medium text-stone-600">
            <span className="flex items-center gap-1 mb-1">
              <CalendarDays className="w-3.5 h-3.5 text-amber-600" /> Nhận phòng
            </span>
            <input
              type="date"
              required
              value={checkIn}
              onChange={(e) => handleCheckInChange(e.target.value)}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </label>

          <label className="block text-xs font-medium text-stone-600">
            <span className="flex items-center gap-1 mb-1">
              <CalendarDays className="w-3.5 h-3.5 text-amber-600" /> Trả phòng
            </span>
            <input
              type="date"
              required
              disabled={!checkIn}
              min={getNextDay(checkIn) || undefined}
              value={checkOut}
              onChange={(e) => handleCheckOutChange(e.target.value)}
              className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-100 disabled:text-stone-400 disabled:cursor-not-allowed"
            />
          </label>

          <div className="flex gap-2 items-end">
            <label className="block text-xs font-medium text-stone-600 w-24">
              <span className="flex items-center gap-1 mb-1">
                <Users className="w-3.5 h-3.5 text-amber-600" /> Khách
              </span>
              <input
                type="number"
                min="1"
                max="10"
                value={sucChua}
                onChange={(e) => setSucChua(Number(e.target.value))}
                className="w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </label>
            <button
              type="submit"
              disabled={searching}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-semibold text-sm px-4 py-2.5 disabled:opacity-50"
            >
              <Search className="w-4 h-4" />
              {searching ? "Đang tìm..." : "Tìm phòng"}
            </button>
          </div>
        </form>

        {selectedBranch && (
          <p className="text-xs text-stone-300 mt-3">
            📍 {selectedBranch.DiaChi} · Hotline: {selectedBranch.SDT} · Quy mô: {selectedBranch.TongSoPhong} phòng
          </p>
        )}
      </section>

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

      {/* Search Results */}
      {searched && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-stone-900 flex items-center gap-2">
              <Hotel className="w-5 h-5 text-amber-600" />
              Phòng khả dụng ({rooms.length} phòng)
            </h2>
            <span className="text-xs text-stone-500">
              Từ {formatDate(checkIn)} đến {formatDate(checkOut)}
            </span>
          </div>

          {rooms.length === 0 ? (
            <div className="rounded-xl border border-stone-200 bg-white p-8 text-center text-sm text-stone-500">
              Không có phòng trống phù hợp cho khoảng ngày này. Hãy thử chi nhánh hoặc ngày khác.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {rooms.map((room) => {
                const total = Number(room.GiaTamTinhChinhXac ?? room.GiaTamTinh ?? 0);
                return (
                  <div
                    key={room.MaPhong}
                    className="rounded-xl border border-stone-200 bg-white p-5 shadow-xs flex flex-col justify-between gap-4 hover:border-amber-300 transition-colors"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <span className="text-xs font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200">
                            Phòng {room.SoPhong} · Tầng {room.Tang}
                          </span>
                          <h3 className="font-bold text-stone-900 mt-2">{room.TenLP}</h3>
                        </div>
                        <Badge status={room.TrangThaiHienTai} />
                      </div>
                      <p className="text-xs text-stone-500 mt-1">
                        Sức chứa tối đa: {room.SucChua} khách · Thời gian: {room.SoDem} đêm
                      </p>
                    </div>

                    <div className="pt-3 border-t border-stone-100 flex items-end justify-between gap-3">
                      <div>
                        <p className="text-xs text-stone-500">
                          Đêm đầu: {formatVND(room.DonGiaDemDau)}
                        </p>
                        <p className="text-lg font-bold text-amber-700">{formatVND(total)}</p>
                        <p className="text-[11px] text-stone-400">Tổng dự kiến ({room.SoDem} đêm)</p>
                      </div>
                      <button
                        onClick={() => {
                          if (!user) {
                            onRequireLogin();
                            return;
                          }
                          setBookingRoom(room);
                          setSelectedComboId("");
                        }}
                        className="rounded-lg bg-stone-900 hover:bg-stone-800 text-white text-xs font-semibold px-4 py-2.5"
                      >
                        Đặt phòng này
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      {/* Booking Confirm Modal */}
      {bookingRoom && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-900/50 p-4 backdrop-blur-xs">
          <form
            onSubmit={handleCreateBooking}
            className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl border border-stone-200 space-y-4 max-h-[90vh] overflow-y-auto"
          >
            <h3 className="text-lg font-bold text-stone-900">
              Xác nhận đặt phòng {bookingRoom.SoPhong} ({bookingRoom.TenLP})
            </h3>
            <div className="rounded-xl bg-stone-50 border border-stone-200 p-3 text-sm space-y-1">
              <p>
                <span className="text-stone-500">Chi nhánh:</span>{" "}
                <strong>{selectedBranch?.TenCN}</strong>
              </p>
              <p>
                <span className="text-stone-500">Lưu trú:</span>{" "}
                <strong>
                  {formatDate(checkIn)} → {formatDate(checkOut)} ({bookingRoom.SoDem} đêm)
                </strong>
              </p>
              <p>
                <span className="text-stone-500">Tổng tiền dự kiến:</span>{" "}
                <strong className="text-amber-700">
                  {formatVND(bookingRoom.GiaTamTinhChinhXac ?? bookingRoom.GiaTamTinh)}
                </strong>
              </p>
            </div>

            {!user?.MaKH && (
              <div className="rounded-xl border border-stone-200 p-3 bg-stone-50/70 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-stone-700">
                    Chọn khách hàng (đặt hộ tại quầy)
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowNewCustomer((v) => !v)}
                    className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 hover:underline"
                  >
                    <UserPlus className="w-3.5 h-3.5" />
                    {showNewCustomer ? "Tìm khách có sẵn" : "Tạo khách walk-in mới"}
                  </button>
                </div>

                {showNewCustomer ? (
                  <div className="space-y-2 text-xs">
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        placeholder="Họ tên *"
                        value={newCustomer.ho_ten}
                        onChange={(e) => setNewCustomer({ ...newCustomer, ho_ten: e.target.value })}
                        className="rounded-lg border border-stone-300 bg-white px-2.5 py-1.5"
                      />
                      <input
                        placeholder="CCCD *"
                        value={newCustomer.cccd}
                        onChange={(e) => setNewCustomer({ ...newCustomer, cccd: e.target.value })}
                        className="rounded-lg border border-stone-300 bg-white px-2.5 py-1.5"
                      />
                      <input
                        placeholder="SĐT *"
                        value={newCustomer.sdt}
                        onChange={(e) => setNewCustomer({ ...newCustomer, sdt: e.target.value })}
                        className="rounded-lg border border-stone-300 bg-white px-2.5 py-1.5"
                      />
                      <input
                        placeholder="Email"
                        value={newCustomer.email}
                        onChange={(e) => setNewCustomer({ ...newCustomer, email: e.target.value })}
                        className="rounded-lg border border-stone-300 bg-white px-2.5 py-1.5"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleQuickCreateCustomer}
                      className="rounded-lg bg-stone-900 text-white px-3 py-1.5 font-medium"
                    >
                      Lưu &amp; Chọn khách này
                    </button>
                  </div>
                ) : (
                  <>
                    <input
                      type="search"
                      placeholder="Tìm theo tên, SĐT, CCCD hoặc MaKH..."
                      value={customerSearch}
                      onChange={(e) => setCustomerSearch(e.target.value)}
                      className="w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-xs"
                    />
                    <select
                      required
                      value={maKhInput}
                      onChange={(e) => setMaKhInput(e.target.value)}
                      className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm"
                    >
                      <option value="">-- Chọn khách hàng --</option>
                      {customerResults.map((c) => (
                        <option key={c.MaKH} value={c.MaKH}>
                          #{c.MaKH} — {c.HoTen} ({c.SDT} · CCCD: {c.CCCD || "—"})
                        </option>
                      ))}
                    </select>
                  </>
                )}
              </div>
            )}

            {roomCombos.length > 0 && (
              <label className="block text-xs font-medium text-stone-700">
                Chọn kèm gói Combo (tùy chọn)
                <select
                  value={selectedComboId}
                  onChange={(e) => setSelectedComboId(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
                >
                  <option value="">Không chọn Combo (theo giá phòng niêm yết)</option>
                  {roomCombos.map((c) => (
                    <option key={c.MaCombo} value={c.MaCombo}>
                      {c.TenCombo} — {formatVND(c.GiaGoi)}
                    </option>
                  ))}
                </select>
              </label>
            )}

            {ticketTypes.length > 0 && (
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-900">
                  <Ticket className="w-3.5 h-3.5 text-emerald-700" />
                  Đặt kèm Vé khu vui chơi tại chi nhánh (tùy chọn)
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <select
                    value={selectedTicketTypeId}
                    onChange={(e) => setSelectedTicketTypeId(e.target.value)}
                    className="sm:col-span-2 rounded-lg border border-stone-300 px-2.5 py-2 text-xs bg-white"
                  >
                    <option value="">Chỉ đặt phòng khách sạn</option>
                    {ticketTypes.map((lv) => (
                      <option key={lv.MaLoaiVe} value={lv.MaLoaiVe}>
                        {lv.TenKhu} — {lv.TenLoaiVe} ({formatVND(lv.GiaVe)}/vé)
                      </option>
                    ))}
                  </select>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    disabled={!selectedTicketTypeId}
                    value={selectedTicketQty}
                    onChange={(e) => setSelectedTicketQty(e.target.value)}
                    placeholder="Số vé"
                    className="rounded-lg border border-stone-300 px-2.5 py-2 text-xs bg-white disabled:bg-stone-100"
                  />
                </div>
              </div>
            )}

            {activeVouchers.length > 0 && (
              <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3 space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-amber-900 flex items-center gap-1.5">
                    <Tag className="w-3.5 h-3.5 text-amber-700" />
                    Tự chọn Voucher áp dụng ({selectedVoucherCodes.length}/
                    {holidayInfo.is_holiday ? (hasAmusementTicket ? 1 : 0) : hasAmusementTicket ? 2 : 1})
                  </span>
                  {holidayInfo.is_holiday ? (
                    <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 text-[11px] font-semibold">
                      Kỳ nghỉ lễ: {holidayInfo.holiday_names.join(", ")}
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[11px] font-semibold">
                      Ngày thường
                    </span>
                  )}
                </div>

                <p className="text-[11px] text-amber-900/90">
                  {holidayInfo.is_holiday
                    ? hasAmusementTicket
                      ? "Ngày lễ (Khách sạn + Khu vui chơi): bạn được chọn tối đa 1 voucher (1 trong 2 loại)."
                      : "Ngày lễ khi chỉ đặt phòng khách sạn không áp dụng voucher (chọn thêm vé khu vui chơi để mở khóa 1 voucher)."
                    : hasAmusementTicket
                    ? "Ngày thường (Khách sạn + Khu vui chơi): chọn tối đa 2 voucher (1 Khách sạn + 1 Khu vui chơi)."
                    : "Ngày thường (Chỉ đặt khách sạn): chọn tối đa 1 voucher Khách sạn."}
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-40 overflow-y-auto pr-1">
                  {activeVouchers.map((v) => {
                    const selected = selectedVoucherCodes.includes(v.Code);
                    const disabledReason = getVoucherDisabledReason(v);
                    const disabled = Boolean(disabledReason);
                    return (
                      <button
                        key={v.MaVoucher}
                        type="button"
                        disabled={disabled}
                        title={disabledReason || undefined}
                        onClick={() => handleToggleVoucher(v)}
                        className={`text-left rounded-lg border px-2.5 py-2 text-xs transition-colors ${
                          selected
                            ? "border-amber-600 bg-white ring-2 ring-amber-400/50"
                            : disabled
                            ? "border-stone-200 bg-stone-100 text-stone-400 cursor-not-allowed opacity-60"
                            : "border-amber-200 bg-white hover:border-amber-400"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1">
                          <span className="font-mono font-bold text-stone-900">{v.Code}</span>
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                              v.LoaiApDung === "Khu vui chơi"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-sky-100 text-sky-800"
                            }`}
                          >
                            {v.LoaiApDung || "Khách sạn"}
                          </span>
                        </div>
                        <p className="text-[11px] text-stone-600 mt-0.5">
                          Giảm{" "}
                          {v.LoaiGiam === "Phần trăm"
                            ? `${v.GiaTriGiam}% (tối đa ${formatVND(v.GiamToiDa)})`
                            : formatVND(v.GiaTriGiam)}{" "}
                          · Tối thiểu {formatVND(v.DonHangToiThieu)}
                        </p>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <label className="block text-xs font-medium text-stone-700">
              Ghi chú yêu cầu
              <textarea
                rows={2}
                placeholder="Nhận phòng muộn, tầng cao, view biển..."
                value={ghiChu}
                onChange={(e) => setGhiChu(e.target.value)}
                className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
              />
            </label>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setBookingRoom(null)}
                className="px-4 py-2 rounded-lg border border-stone-300 text-sm text-stone-700"
              >
                Đóng
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-sm font-semibold disabled:opacity-50"
              >
                {submitting ? "Đang tạo đơn..." : "Xác nhận đặt phòng"}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Combos & Vouchers */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3">
          <h2 className="font-bold text-stone-900 flex items-center gap-2">
            <Gift className="w-5 h-5 text-amber-600" />
            Gói Combo tại {selectedBranch?.TenCN || "chi nhánh"} ({combos.length})
          </h2>
          {combos.length === 0 ? (
            <p className="text-xs text-stone-500">Chưa có gói combo riêng cho chi nhánh này.</p>
          ) : (
            <div className="space-y-2.5">
              {combos.map((c) => (
                <div
                  key={c.MaCombo}
                  className="rounded-xl border border-stone-200 bg-stone-50 p-3.5 text-sm"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold text-stone-900">{c.TenCombo}</p>
                      <p className="text-xs text-stone-500 mt-0.5">
                        {c.TenLP} · {c.SoNgayLuuTru} ngày ·{" "}
                        {[
                          c.BaoGomBuffet ? "Buffet" : null,
                          c.BaoGomVeVuiChoi ? "Vé vui chơi" : null,
                          c.BaoGomDonSanBay ? "Đón sân bay" : null,
                        ]
                          .filter(Boolean)
                          .join(" + ")}
                      </p>
                    </div>
                    <span className="font-bold text-amber-700 whitespace-nowrap">
                      {formatVND(c.GiaGoi)}
                    </span>
                  </div>
                  {c.MoTa && <p className="text-xs text-stone-600 mt-1.5">{c.MoTa}</p>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3">
          <h2 className="font-bold text-stone-900 flex items-center gap-2">
            <Tag className="w-5 h-5 text-amber-600" />
            Mã giảm giá / Voucher ({vouchers.length})
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-h-72 overflow-y-auto pr-1">
            {vouchers.map((v) => (
              <div
                key={v.MaVoucher}
                className="rounded-xl border border-dashed border-amber-300 bg-amber-50/40 p-3 text-xs space-y-1"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-bold text-amber-800 text-sm">{v.Code}</span>
                  <div className="flex items-center gap-1">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        v.LoaiApDung === "Khu vui chơi"
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-sky-100 text-sky-800"
                      }`}
                    >
                      {v.LoaiApDung || "Khách sạn"}
                    </span>
                    <Badge status={v.TrangThai} />
                  </div>
                </div>
                <p className="text-stone-700 font-medium">
                  Giảm{" "}
                  {v.LoaiGiam === "Phần trăm"
                    ? `${v.GiaTriGiam}% (tối đa ${formatVND(v.GiamToiDa)})`
                    : formatVND(v.GiaTriGiam)}
                </p>
                <p className="text-stone-500">
                  Đơn tối thiểu: {formatVND(v.DonHangToiThieu)} · HSD:{" "}
                  {formatDate(v.NgayKetThuc)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* My Bookings */}
      <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 className="font-bold text-stone-900 text-lg">
            Đơn đặt phòng &amp; Hóa đơn {user ? `(${myBookings.length})` : ""}
          </h2>
          {user ? (
            <input
              type="search"
              placeholder="Tìm theo #MaDP, số phòng..."
              value={bookingSearchQ}
              onChange={(e) => setBookingSearchQ(e.target.value)}
              className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm bg-white w-56"
            />
          ) : (
            <button
              onClick={onRequireLogin}
              className="text-xs font-semibold text-amber-700 hover:underline"
            >
              Đăng nhập để xem lịch sử đặt phòng →
            </button>
          )}
        </div>

        {user && myBookings.length === 0 && (
          <p className="text-sm text-stone-500">Chưa có đơn đặt phòng nào.</p>
        )}

        {user && myBookings.length > 0 && (
          <div className="space-y-3">
            {myBookings.map((b) => {
              const isOpen = expandedDp === b.MaDP;
              const detail = dpDetailMap[b.MaDP];
              const canCancel = ["Chờ xác nhận", "Đã xác nhận"].includes(b.TrangThaiDatPhong);

              return (
                <div key={b.MaDP} className="rounded-xl border border-stone-200 overflow-hidden">
                  <div className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 bg-stone-50/70">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono font-bold text-stone-900">#{b.MaDP}</span>
                        <Badge status={b.TrangThaiDatPhong} />
                        <span className="text-xs text-stone-500">· {b.TenCN}</span>
                      </div>
                      <p className="text-sm text-stone-700">
                        Phòng <strong>{b.SoPhong}</strong> ({b.TenLP}) ·{" "}
                        {formatDate(b.NgayCheckIn)} → {formatDate(b.NgayCheckOut)} ({b.SoDem} đêm)
                      </p>
                      <p className="text-xs text-stone-500">
                        Khách: {b.TenKhachHang} · Hóa đơn #{b.MaHD || "—"}:{" "}
                        <strong className="text-stone-900">{formatVND(b.TongTienHoaDon)}</strong>{" "}
                        {b.TrangThaiHoaDon && `(${b.TrangThaiHoaDon})`}
                      </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {b.MaHD && b.TrangThaiHoaDon !== "Đã thanh toán" && b.TrangThaiDatPhong !== "Đã hủy" && (
                        <button
                          onClick={() => setPaymentQrState({ maHd: b.MaHD, initialQr: null })}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-amber-300 bg-amber-50 hover:bg-amber-100 text-xs font-semibold text-amber-800"
                        >
                          <QrCode className="w-3.5 h-3.5" /> QR Chuyển tiền
                        </button>
                      )}
                      {b.MaHD && (
                        <button
                          onClick={() => setSelectedHd(b.MaHD)}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-stone-300 bg-white hover:bg-stone-100 text-xs font-medium text-stone-800"
                        >
                          <Receipt className="w-3.5 h-3.5 text-amber-600" /> Hóa đơn
                        </button>
                      )}
                      <button
                        onClick={() => toggleDetail(b.MaDP)}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-stone-300 bg-white hover:bg-stone-100 text-xs font-medium text-stone-700"
                      >
                        {isOpen ? (
                          <>
                            <ChevronUp className="w-3.5 h-3.5" /> Thu gọn
                          </>
                        ) : (
                          <>
                            <ChevronDown className="w-3.5 h-3.5" /> Dịch vụ &amp; Vé QR
                          </>
                        )}
                      </button>
                      {canCancel && (
                        <button
                          onClick={() => setCancelTargetDp(b.MaDP)}
                          className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-rose-200 bg-rose-50 hover:bg-rose-100 text-xs font-medium text-rose-700"
                        >
                          <XCircle className="w-3.5 h-3.5" /> Hủy phòng
                        </button>
                      )}
                    </div>
                  </div>

                  {isOpen && (
                    <div className="p-4 border-t border-stone-200 bg-white grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      <div>
                        <p className="font-semibold text-stone-700 mb-2">Dịch vụ đã sử dụng</p>
                        {!detail ? (
                          <p className="text-stone-400">Đang tải...</p>
                        ) : detail.services.length === 0 ? (
                          <p className="text-stone-400">Chưa sử dụng dịch vụ phát sinh.</p>
                        ) : (
                          <ul className="space-y-1.5">
                            {detail.services.map((s) => (
                              <li
                                key={s.MaSD}
                                className="flex justify-between border-b border-stone-100 pb-1"
                              >
                                <span>
                                  {s.TenDV} × {s.SoLuong}
                                </span>
                                <span className="font-medium">
                                  {formatVND(s.SoLuong * s.DonGiaTaiThoiDiem)}
                                </span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>

                      <div>
                        <p className="font-semibold text-stone-700 mb-2 flex items-center gap-1">
                          <QrCode className="w-3.5 h-3.5 text-amber-600" /> Vé điện tử đính kèm
                        </p>
                        {!detail ? (
                          <p className="text-stone-400">Đang tải...</p>
                        ) : detail.tickets.length === 0 ? (
                          <p className="text-stone-400">Không có vé khu vui chơi.</p>
                        ) : (
                          <ul className="space-y-2.5">
                            {detail.tickets.map((t) => (
                              <li
                                key={t.MaVe}
                                className="flex items-center justify-between gap-3 rounded-lg border border-stone-100 bg-stone-50 p-2.5"
                              >
                                <div className="flex items-center gap-3">
                                  <div className="bg-white p-1 rounded-md border border-stone-200 shrink-0">
                                    <QRCodeSVG value={t.MaQR} size={48} />
                                  </div>
                                  <div>
                                    <span className="font-mono font-semibold text-stone-900">
                                      {t.MaQR}
                                    </span>
                                    <p className="text-stone-600">
                                      {t.TenLoaiVe} ({t.TenKhu})
                                    </p>
                                    {t.ThoiGianQuet && (
                                      <span className="block text-[11px] text-stone-400">
                                        Quét lúc: {formatDateTime(t.ThoiGianQuet)}
                                      </span>
                                    )}
                                  </div>
                                </div>
                                <Badge status={t.TrangThai} />
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <InvoiceModal
        maHd={selectedHd}
        canManage={canManageInvoice}
        onClose={() => setSelectedHd(null)}
        onUpdated={loadMyBookings}
      />

      <CancelBookingModal
        maDp={cancelTargetDp}
        requireOtp={Boolean(user && !user.MaKH)}
        onClose={() => setCancelTargetDp(null)}
        onConfirm={handleCancelBooking}
      />

      <PaymentQrModal
        maHd={paymentQrState.maHd}
        initialQr={paymentQrState.initialQr}
        canConfirmPayment={canManageInvoice}
        onClose={() => setPaymentQrState({ maHd: null, initialQr: null })}
        onPaid={loadMyBookings}
      />
    </div>
  );
}
