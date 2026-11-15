import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  Building2,
  CalendarPlus,
  Clock,
  DollarSign,
  Download,
  Lock,
  RefreshCw,
  Shield,
  Sparkles,
  Unlock,
} from "lucide-react";
import { apiFetch } from "../api/client";
import Badge from "../components/Badge";
import { downloadCSV, formatDateTime, formatVND } from "../utils/format";

export default function AdminDashboardPage({ user }) {
  const [branches, setBranches] = useState([]);
  const [maCn, setMaCn] = useState("");
  const [thang, setThang] = useState("2025-07");

  const [dashboard, setDashboard] = useState(null);
  const [shifts, setShifts] = useState([]);
  const [shiftCatalog, setShiftCatalog] = useState([]);
  const [staffList, setStaffList] = useState([]);
  const [shiftForm, setShiftForm] = useState({
    ma_nv: "",
    ma_ca: "",
    ngay_lam: "2025-07-30",
  });

  const [rbacUsers, setRbacUsers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);

  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const perms = user?.permissions || [];
  const canReadReport = perms.includes("REPORT.READ_BRANCH") || perms.includes("BOOKING.READ_BRANCH");
  const canReadStaff = perms.includes("STAFF.READ_BRANCH");
  const canManageStaff = user?.is_admin || perms.includes("STAFF.MANAGE_BRANCH");
  const isAdmin = Boolean(user?.is_admin);

  const allowedBranches = useMemo(() => {
    if (!user) return [];
    if (isAdmin || !user.branch_ids?.length) return branches;
    return branches.filter((b) => user.branch_ids.includes(b.MaCN));
  }, [branches, user, isAdmin]);

  useEffect(() => {
    apiFetch("/api/catalog/branches")
      .then((all) => {
        setBranches(all);
        if (user && !user.is_admin && user.branch_ids?.length) {
          setMaCn(String(user.branch_ids[0]));
        }
      })
      .catch((err) => setError(err.message));
  }, [user]);

  async function loadAll() {
    if (!user || !canReadReport) return;
    setLoading(true);
    setError("");
    try {
      const qsDash = maCn ? `?ma_cn=${maCn}` : "";
      const tasks = [apiFetch(`/api/admin/dashboard${qsDash}`)];

      if (canReadStaff) {
        const qsShift = new URLSearchParams({ thang });
        if (maCn) qsShift.set("ma_cn", maCn);
        tasks.push(apiFetch(`/api/admin/staff-shifts?${qsShift}`));
        tasks.push(apiFetch("/api/admin/shifts-catalog"));
        tasks.push(apiFetch(`/api/admin/staff-list${qsDash}`));
      } else {
        tasks.push(Promise.resolve([]), Promise.resolve([]), Promise.resolve([]));
      }

      if (isAdmin) {
        tasks.push(apiFetch("/api/admin/users"));
        tasks.push(apiFetch("/api/admin/audit-logs?limit=50"));
      } else {
        tasks.push(Promise.resolve([]), Promise.resolve([]));
      }

      const [d, s, cat, staff, u, logs] = await Promise.all(tasks);
      setDashboard(d);
      setShifts(s);
      setShiftCatalog(cat);
      setStaffList(staff);
      if (staff.length > 0 && !shiftForm.ma_nv) {
        setShiftForm((prev) => ({ ...prev, ma_nv: String(staff[0].MaNV) }));
      }
      if (cat.length > 0 && !shiftForm.ma_ca) {
        setShiftForm((prev) => ({ ...prev, ma_ca: String(cat[0].MaCa) }));
      }
      setRbacUsers(u);
      setAuditLogs(logs);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
  }, [user, maCn, thang]);

  async function handleAssignShift(e) {
    e.preventDefault();
    setError("");
    setNotice("");
    try {
      const res = await apiFetch("/api/admin/staff-shifts", {
        method: "POST",
        body: JSON.stringify({
          ma_nv: Number(shiftForm.ma_nv),
          ma_ca: Number(shiftForm.ma_ca),
          ngay_lam: shiftForm.ngay_lam,
        }),
      });
      setNotice(res.message);
      setThang(shiftForm.ngay_lam.slice(0, 7));
      await loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleToggleUserStatus(target) {
    const nextStatus = target.TrangThaiTaiKhoan === "Hoạt động" ? "Bị khóa" : "Hoạt động";
    setError("");
    setNotice("");
    try {
      const res = await apiFetch(`/api/admin/users/${target.MaTK}/status`, {
        method: "PATCH",
        body: JSON.stringify({ trang_thai: nextStatus }),
      });
      setNotice(res.message);
      await loadAll();
    } catch (err) {
      setError(err.message);
    }
  }

  if (!canReadReport) {
    return (
      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-800">
        Tài khoản hiện tại không có quyền xem Báo cáo &amp; Quản trị. Vui lòng đăng nhập bằng tài khoản{" "}
        <strong>quanly_cn1</strong>, <strong>letan_cn1</strong> hoặc <strong>admin_hethong</strong>.
      </div>
    );
  }

  const revBranch = dashboard?.revenue_by_branch || [];
  const revMonth = dashboard?.revenue_by_month || [];
  const occupancy = dashboard?.room_occupancy || [];
  const topServices = dashboard?.top_services || [];

  const totalRevenue = revBranch.reduce((a, r) => a + Number(r.TongDoanhThu || 0), 0);
  const totalCollected = revBranch.reduce((a, r) => a + Number(r.TongDaThu || 0), 0);
  const totalDebt = revBranch.reduce((a, r) => a + Number(r.CongNo || 0), 0);
  const totalInvoices = revBranch.reduce((a, r) => a + Number(r.SoHoaDon || 0), 0);

  const totalRooms = occupancy.reduce((a, r) => a + Number(r.TongSoPhong || 0), 0);
  const usedRooms = occupancy.reduce((a, r) => a + Number(r.SoPhongDangSuDung || 0), 0);
  const avgOccupancy = totalRooms > 0 ? ((usedRooms / totalRooms) * 100).toFixed(1) : "0.0";

  const maxBranchRev = Math.max(1, ...revBranch.map((r) => Number(r.TongDoanhThu || 0)));
  const maxMonthRev = Math.max(1, ...revMonth.map((r) => Number(r.TongDoanhThu || 0)));

  return (
    <div className="space-y-6">
      {/* Toolbar */}
      <div className="rounded-2xl border border-stone-200 bg-white p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-stone-900 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-amber-600" />
            Dashboard Quản lý, Phân ca &amp; Nhật ký Audit
          </h1>
          <p className="text-xs text-stone-500 mt-0.5">
            Tổng hợp doanh thu từ <code className="bg-stone-100 px-1 rounded-sm">vw_doanh_thu_chi_nhanh</code>, công suất phòng{" "}
            <code className="bg-stone-100 px-1 rounded-sm">vw_cong_suat_phong_chi_nhanh</code> và phân quyền RBAC.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={maCn}
            onChange={(e) => {
              setMaCn(e.target.value);
              setShiftForm((prev) => ({ ...prev, ma_nv: "" }));
            }}
            className="rounded-lg border border-stone-300 px-3 py-2 text-sm bg-white"
          >
            {isAdmin && <option value="">Tất cả 10 chi nhánh</option>}
            {allowedBranches.map((b) => (
              <option key={b.MaCN} value={b.MaCN}>
                CN #{b.MaCN} — {b.TenCN}
              </option>
            ))}
          </select>

          <button
            onClick={loadAll}
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

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-1">
          <p className="text-xs font-medium text-stone-500 flex items-center gap-1.5">
            <DollarSign className="w-4 h-4 text-amber-600" /> Tổng doanh thu ({totalInvoices} HĐ)
          </p>
          <p className="text-2xl font-bold text-stone-900">{formatVND(totalRevenue)}</p>
        </div>
        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-1">
          <p className="text-xs font-medium text-stone-500 flex items-center gap-1.5">
            <DollarSign className="w-4 h-4 text-emerald-600" /> Thực thu đã ghi nhận
          </p>
          <p className="text-2xl font-bold text-emerald-700">{formatVND(totalCollected)}</p>
        </div>
        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-1">
          <p className="text-xs font-medium text-stone-500 flex items-center gap-1.5">
            <DollarSign className="w-4 h-4 text-rose-600" /> Công nợ còn phải thu
          </p>
          <p className="text-2xl font-bold text-rose-700">{formatVND(totalDebt)}</p>
        </div>
        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-1">
          <p className="text-xs font-medium text-stone-500 flex items-center gap-1.5">
            <Building2 className="w-4 h-4 text-sky-600" /> Công suất đang sử dụng
          </p>
          <p className="text-2xl font-bold text-stone-900">
            {avgOccupancy}%{" "}
            <span className="text-xs font-normal text-stone-500">
              ({usedRooms}/{totalRooms} phòng)
            </span>
          </p>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-stone-900">Doanh thu theo chi nhánh</h2>
            {revBranch.length > 0 && (
              <button
                type="button"
                onClick={() =>
                  downloadCSV(
                    "doanh_thu_chi_nhanh.csv",
                    ["MaCN", "TenCN", "SoHoaDon", "TongDoanhThu", "TongDaThu", "CongNo"],
                    revBranch.map((r) => [
                      r.MaCN,
                      r.TenCN,
                      r.SoHoaDon,
                      r.TongDoanhThu,
                      r.TongDaThu,
                      r.CongNo,
                    ])
                  )
                }
                className="inline-flex items-center gap-1 text-xs font-medium text-stone-700 border border-stone-300 rounded-lg px-2.5 py-1 hover:bg-stone-50"
              >
                <Download className="w-3.5 h-3.5" /> Xuất CSV
              </button>
            )}
          </div>
          <div className="space-y-3">
            {revBranch.map((r) => {
              const pct = Math.round((Number(r.TongDoanhThu || 0) / maxBranchRev) * 100);
              return (
                <div key={r.MaCN} className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="font-medium text-stone-800">{r.TenCN}</span>
                    <span className="font-bold text-stone-900">
                      {formatVND(r.TongDoanhThu)} ({r.SoHoaDon} HĐ)
                    </span>
                  </div>
                  <div className="h-2.5 w-full rounded-full bg-stone-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-amber-600 transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
          <h2 className="font-bold text-stone-900">Doanh thu theo tháng</h2>
          <div className="space-y-3">
            {revMonth.map((m) => {
              const pct = Math.round((Number(m.TongDoanhThu || 0) / maxMonthRev) * 100);
              return (
                <div key={m.ThangLap} className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="font-mono font-medium text-stone-800">{m.ThangLap}</span>
                    <span className="font-bold text-stone-900">
                      {formatVND(m.TongDoanhThu)} ({m.SoHoaDon} HĐ)
                    </span>
                  </div>
                  <div className="h-2.5 w-full rounded-full bg-stone-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-stone-800 transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Room Occupancy + Top Services */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3">
          <h2 className="font-bold text-stone-900">Công suất phòng từng chi nhánh</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="border-b border-stone-200 text-stone-500 uppercase bg-stone-50">
                  <th className="py-2 px-2">Chi nhánh</th>
                  <th className="py-2 px-2 text-right">Tổng</th>
                  <th className="py-2 px-2 text-right">Trống</th>
                  <th className="py-2 px-2 text-right">Đang dùng</th>
                  <th className="py-2 px-2 text-right">Sẵn sàng</th>
                  <th className="py-2 px-2 text-right">Bảo trì</th>
                  <th className="py-2 px-2 text-right">% SD</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {occupancy.map((o) => (
                  <tr key={o.MaCN} className="hover:bg-stone-50">
                    <td className="py-2 px-2 font-medium text-stone-900">{o.TenCN}</td>
                    <td className="py-2 px-2 text-right">{o.TongSoPhong}</td>
                    <td className="py-2 px-2 text-right text-emerald-700">{o.SoPhongTrong}</td>
                    <td className="py-2 px-2 text-right text-amber-700 font-semibold">
                      {o.SoPhongDangSuDung}
                    </td>
                    <td className="py-2 px-2 text-right text-teal-700">{o.SoPhongSanSang}</td>
                    <td className="py-2 px-2 text-right text-rose-700">{o.SoPhongBaoTri}</td>
                    <td className="py-2 px-2 text-right font-bold">{o.TyLeDangSuDungPct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3">
          <h2 className="font-bold text-stone-900 flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-amber-600" /> Top dịch vụ doanh thu cao nhất
          </h2>
          <div className="space-y-2">
            {topServices.map((s) => (
              <div
                key={s.MaDV}
                className="flex items-center justify-between gap-3 rounded-xl border border-stone-100 bg-stone-50 px-3 py-2.5 text-xs"
              >
                <div>
                  <p className="font-semibold text-stone-900">{s.TenDV}</p>
                  <p className="text-stone-500">
                    {s.LoaiDV} · {s.TongLuot} lượt ({s.TongSoLuong} đơn vị)
                  </p>
                </div>
                <span className="font-bold text-amber-700 whitespace-nowrap">
                  {formatVND(s.TongDoanhThu)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Staff Shifts */}
      {canReadStaff && (
        <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h2 className="font-bold text-stone-900 flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-600" />
              Bảng công &amp; phân ca nhân viên ({shifts.length})
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-xs text-stone-600 flex items-center gap-2">
                Tháng:
                <input
                  type="month"
                  value={thang}
                  onChange={(e) => setThang(e.target.value)}
                  className="rounded-lg border border-stone-300 px-2.5 py-1 text-xs bg-white"
                />
              </label>
              {shifts.length > 0 && (
                <button
                  type="button"
                  onClick={() =>
                    downloadCSV(
                      `bang_cong_${thang}.csv`,
                      ["MaCN", "TenCN", "MaNV", "HoTen", "ChucVu", "SoCaLam", "TongSoGio"],
                      shifts.map((sh) => [
                        sh.MaCN,
                        sh.TenCN,
                        sh.MaNV,
                        sh.HoTen,
                        sh.ChucVu,
                        sh.SoCaLam,
                        sh.TongSoGio,
                      ])
                    )
                  }
                  className="inline-flex items-center gap-1 text-xs font-medium text-stone-700 border border-stone-300 rounded-lg px-2.5 py-1 hover:bg-stone-50"
                >
                  <Download className="w-3.5 h-3.5" /> Xuất CSV
                </button>
              )}
            </div>
          </div>

          {canManageStaff && staffList.length > 0 && shiftCatalog.length > 0 && (
            <form
              onSubmit={handleAssignShift}
              className="grid grid-cols-1 sm:grid-cols-4 gap-2.5 rounded-xl bg-stone-50 border border-stone-200 p-3 text-xs"
            >
              <select
                required
                value={shiftForm.ma_nv}
                onChange={(e) => setShiftForm({ ...shiftForm, ma_nv: e.target.value })}
                className="rounded-lg border border-stone-300 bg-white px-2.5 py-1.5"
              >
                {staffList.map((nv) => (
                  <option key={nv.MaNV} value={nv.MaNV}>
                    #{nv.MaNV} — {nv.HoTen} ({nv.ChucVu})
                  </option>
                ))}
              </select>
              <select
                required
                value={shiftForm.ma_ca}
                onChange={(e) => setShiftForm({ ...shiftForm, ma_ca: e.target.value })}
                className="rounded-lg border border-stone-300 bg-white px-2.5 py-1.5"
              >
                {shiftCatalog.map((c) => (
                  <option key={c.MaCa} value={c.MaCa}>
                    {c.TenCa} ({String(c.GioBD).slice(0, 5)}–{String(c.GioKT).slice(0, 5)})
                  </option>
                ))}
              </select>
              <input
                type="date"
                required
                value={shiftForm.ngay_lam}
                onChange={(e) => setShiftForm({ ...shiftForm, ngay_lam: e.target.value })}
                className="rounded-lg border border-stone-300 bg-white px-2.5 py-1.5"
              />
              <button
                type="submit"
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-stone-900 hover:bg-stone-800 text-white font-semibold px-3 py-1.5"
              >
                <CalendarPlus className="w-3.5 h-3.5 text-amber-400" /> Xếp ca làm
              </button>
            </form>
          )}

          <div className="overflow-x-auto max-h-72 overflow-y-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="border-b border-stone-200 text-stone-500 uppercase bg-stone-50">
                  <th className="py-2 px-3">Chi nhánh</th>
                  <th className="py-2 px-3">Mã NV</th>
                  <th className="py-2 px-3">Họ tên</th>
                  <th className="py-2 px-3">Chức vụ</th>
                  <th className="py-2 px-3 text-right">Số ca</th>
                  <th className="py-2 px-3 text-right">Tổng giờ công</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {shifts.map((sh) => (
                  <tr key={sh.MaNV} className="hover:bg-stone-50">
                    <td className="py-2 px-3">{sh.TenCN}</td>
                    <td className="py-2 px-3 font-mono">#{sh.MaNV}</td>
                    <td className="py-2 px-3 font-medium text-stone-900">{sh.HoTen}</td>
                    <td className="py-2 px-3">{sh.ChucVu}</td>
                    <td className="py-2 px-3 text-right">{sh.SoCaLam}</td>
                    <td className="py-2 px-3 text-right font-bold">{sh.TongSoGio}h</td>
                  </tr>
                ))}
                {shifts.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-stone-400">
                      Không có dữ liệu phân ca trong tháng {thang}.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Admin Only: RBAC Matrix & Audit Logs */}
      {isAdmin && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3">
            <h2 className="font-bold text-stone-900 flex items-center gap-2">
              <Shield className="w-4 h-4 text-amber-600" />
              Ma trận tài khoản RBAC ({rbacUsers.length})
            </h2>
            <div className="overflow-x-auto max-h-80 overflow-y-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-stone-200 text-stone-500 uppercase bg-stone-50">
                    <th className="py-2 px-2">Tài khoản</th>
                    <th className="py-2 px-2">Vai trò</th>
                    <th className="py-2 px-2">Phạm vi CN</th>
                    <th className="py-2 px-2 text-right">Số quyền</th>
                    <th className="py-2 px-2">Trạng thái</th>
                    <th className="py-2 px-2 text-right">Thao tác</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {rbacUsers.map((u) => {
                    const isSelf = u.MaTK === user.MaTK;
                    const locked = u.TrangThaiTaiKhoan !== "Hoạt động";
                    return (
                      <tr key={u.MaTK} className="hover:bg-stone-50">
                        <td className="py-2 px-2 font-mono font-semibold text-stone-900">
                          {u.TenDangNhap}
                        </td>
                        <td className="py-2 px-2">{u.VaiTro || "—"}</td>
                        <td className="py-2 px-2">{u.ChiNhanh || "Toàn chuỗi"}</td>
                        <td className="py-2 px-2 text-right font-semibold">{u.SoQuyen}</td>
                        <td className="py-2 px-2">
                          <Badge status={u.TrangThaiTaiKhoan} />
                        </td>
                        <td className="py-2 px-2 text-right">
                          {!isSelf && (
                            <button
                              type="button"
                              onClick={() => handleToggleUserStatus(u)}
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-[11px] font-medium ${
                                locked
                                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                  : "border-rose-200 bg-rose-50 text-rose-700"
                              }`}
                            >
                              {locked ? (
                                <>
                                  <Unlock className="w-3 h-3" /> Mở khóa
                                </>
                              ) : (
                                <>
                                  <Lock className="w-3 h-3" /> Khóa
                                </>
                              )}
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl border border-stone-200 bg-white p-5 space-y-3">
            <h2 className="font-bold text-stone-900 flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-600" />
              Nhật ký hoạt động hệ thống ({auditLogs.length})
            </h2>
            <div className="overflow-x-auto max-h-80 overflow-y-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead>
                  <tr className="border-b border-stone-200 text-stone-500 uppercase bg-stone-50">
                    <th className="py-2 px-2">Thời gian</th>
                    <th className="py-2 px-2">User</th>
                    <th className="py-2 px-2">Hành động</th>
                    <th className="py-2 px-2">Bảng / Khóa</th>
                    <th className="py-2 px-2">Lý do</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {auditLogs.map((l) => (
                    <tr key={l.MaNhatKy} className="hover:bg-stone-50">
                      <td className="py-2 px-2 whitespace-nowrap text-stone-500">
                        {formatDateTime(l.ThoiGian)}
                      </td>
                      <td className="py-2 px-2 font-mono">{l.TenDangNhap || `#${l.MaTK}`}</td>
                      <td className="py-2 px-2 font-semibold text-stone-900">{l.HanhDong}</td>
                      <td className="py-2 px-2 font-mono">
                        {l.BangDuLieu}:{l.KhoaBanGhi}
                      </td>
                      <td className="py-2 px-2 text-stone-600">{l.LyDo}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
