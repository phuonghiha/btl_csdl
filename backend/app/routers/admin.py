from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import fetch_all, fetch_one, get_cursor
from ..security import ensure_branch_access, get_current_user, require_permission

router = APIRouter(prefix="/api/admin", tags=["Dashboard, Nhân sự & Quản trị"])


def _branch_filter_clause(user: dict, ma_cn: int | None, col: str = "MaCN") -> tuple[str, list[Any]]:
    if ma_cn is not None:
        ensure_branch_access(user, ma_cn)
        return f"WHERE {col} = %s", [ma_cn]
    if user["is_admin"]:
        return "", []
    if not user["branch_ids"]:
        return "WHERE 1 = 0", []
    ph = ", ".join(["%s"] * len(user["branch_ids"]))
    return f"WHERE {col} IN ({ph})", list(user["branch_ids"])


@router.get("/dashboard")
def get_dashboard_summary(
    ma_cn: int | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    if not (
        user["is_admin"]
        or "REPORT.READ_BRANCH" in user["permissions"]
        or "BOOKING.READ_BRANCH" in user["permissions"]
    ):
        raise HTTPException(status_code=403, detail="Không có quyền xem dashboard")

    where_sql, params = _branch_filter_clause(user, ma_cn)

    revenue_by_branch = fetch_all(
        f"""
        SELECT MaCN, TenCN,
               SUM(SoHoaDon) AS SoHoaDon,
               SUM(TongTienHoaDon) AS TongDoanhThu,
               SUM(TongTienDaThu) AS TongDaThu,
               SUM(CongNoConLai) AS CongNo
        FROM vw_doanh_thu_chi_nhanh
        {where_sql}
        GROUP BY MaCN, TenCN
        ORDER BY TongDoanhThu DESC
        """,
        params,
    )

    revenue_by_month = fetch_all(
        f"""
        SELECT ThangLap,
               SUM(SoHoaDon) AS SoHoaDon,
               SUM(TongTienHoaDon) AS TongDoanhThu
        FROM vw_doanh_thu_chi_nhanh
        {where_sql}
        GROUP BY ThangLap
        ORDER BY ThangLap
        """,
        params,
    )

    room_occupancy = fetch_all(
        f"SELECT * FROM vw_cong_suat_phong_chi_nhanh {where_sql} ORDER BY MaCN",
        params,
    )

    top_services = fetch_all(
        f"""
        SELECT MaDV, TenDV, LoaiDV,
               SUM(SoLuotSuDung) AS TongLuot,
               SUM(TongSoLuong) AS TongSoLuong,
               SUM(TongDoanhThuDV) AS TongDoanhThu
        FROM vw_su_dung_dich_vu_chi_tiet
        {where_sql}
        GROUP BY MaDV, TenDV, LoaiDV
        ORDER BY TongDoanhThu DESC
        LIMIT 8
        """,
        params,
    )

    return {
        "revenue_by_branch": revenue_by_branch,
        "revenue_by_month": revenue_by_month,
        "room_occupancy": room_occupancy,
        "top_services": top_services,
    }


@router.get("/staff-shifts")
def get_staff_shifts(
    ma_cn: int | None = Query(default=None),
    thang: str = Query(default="2025-07", pattern=r"^\d{4}-\d{2}$"),
    user: dict = Depends(get_current_user),
):
    if not (user["is_admin"] or "STAFF.READ_BRANCH" in user["permissions"]):
        raise HTTPException(status_code=403, detail="Không có quyền xem lịch ca nhân viên")

    where_sql, params = _branch_filter_clause(user, ma_cn, col="cn.MaCN")
    month_start = f"{thang}-01"
    range_cond = "pc.NgayLam >= %s AND pc.NgayLam < DATE_ADD(%s, INTERVAL 1 MONTH)"
    if where_sql:
        where_sql += f" AND {range_cond}"
    else:
        where_sql = f"WHERE {range_cond}"
    params.extend([month_start, month_start])

    return fetch_all(
        f"""
        SELECT cn.MaCN, cn.TenCN, nv.MaNV, nv.HoTen, nv.ChucVu,
               COUNT(pc.MaPhanCa) AS SoCaLam,
               ROUND(SUM(
                   CASE
                       WHEN cl.GioKT >= cl.GioBD
                           THEN TIME_TO_SEC(TIMEDIFF(cl.GioKT, cl.GioBD)) / 3600.0
                       ELSE (86400 - TIME_TO_SEC(cl.GioBD) + TIME_TO_SEC(cl.GioKT)) / 3600.0
                   END
               ), 2) AS TongSoGio
        FROM PHAN_CA pc
        JOIN NHAN_VIEN nv ON nv.MaNV = pc.MaNV
        JOIN CHI_NHANH cn ON cn.MaCN = nv.MaCN
        JOIN CA_LAM cl ON cl.MaCa = pc.MaCa
        {where_sql}
        GROUP BY cn.MaCN, cn.TenCN, nv.MaNV, nv.HoTen, nv.ChucVu
        ORDER BY cn.MaCN, TongSoGio DESC, nv.MaNV
        """,
        params,
    )


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = Query(default=100, ge=1, le=300),
    user: dict = Depends(get_current_user),
):
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Chỉ Admin mới được xem nhật ký toàn hệ thống")

    return fetch_all(
        """
        SELECT nk.MaNhatKy, nk.MaTK, tk.TenDangNhap, nk.HanhDong, nk.BangDuLieu,
               nk.KhoaBanGhi, nk.GiaTriCu, nk.GiaTriMoi, nk.LyDo, nk.ThoiGian
        FROM NHAT_KY_HOAT_DONG nk
        LEFT JOIN TAI_KHOAN tk ON tk.MaTK = nk.MaTK
        ORDER BY nk.MaNhatKy DESC
        LIMIT %s
        """,
        (limit,),
    )


@router.get("/users")
def list_rbac_users(user: dict = Depends(get_current_user)):
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Chỉ Admin mới được xem danh sách tài khoản RBAC")

    return fetch_all(
        """
        SELECT MaTK, TenDangNhap, TrangThaiTaiKhoan, MaNV, MaKH,
               GROUP_CONCAT(DISTINCT MaVaiTro ORDER BY MaVaiTro SEPARATOR ', ') AS VaiTro,
               GROUP_CONCAT(DISTINCT MaChiNhanhDuocGiao ORDER BY MaChiNhanhDuocGiao SEPARATOR ', ') AS ChiNhanh,
               COUNT(DISTINCT MaQuyen) AS SoQuyen
        FROM vw_phan_quyen_tai_khoan
        GROUP BY MaTK, TenDangNhap, TrangThaiTaiKhoan, MaNV, MaKH
        ORDER BY MaTK
        """
    )


class AssignShiftRequest(BaseModel):
    ma_nv: int
    ma_ca: int
    ngay_lam: date


class UpdateAccountStatusRequest(BaseModel):
    trang_thai: str = Field(..., pattern="^(Hoạt động|Bị khóa|Chờ xác minh)$")


@router.get("/shifts-catalog")
def list_shift_catalog(user: dict = Depends(require_permission("STAFF.READ_BRANCH"))):
    return fetch_all("SELECT MaCa, TenCa, GioBD, GioKT FROM CA_LAM ORDER BY MaCa")


@router.get("/staff-list")
def list_staff(
    ma_cn: int | None = Query(default=None),
    user: dict = Depends(require_permission("STAFF.READ_BRANCH")),
):
    where_sql, params = _branch_filter_clause(user, ma_cn, col="nv.MaCN")
    return fetch_all(
        f"""
        SELECT nv.MaNV, nv.MaCN, cn.TenCN, nv.HoTen, nv.ChucVu, nv.SDT, nv.Email
        FROM NHAN_VIEN nv
        JOIN CHI_NHANH cn ON cn.MaCN = nv.MaCN
        {where_sql}
        ORDER BY nv.MaCN, nv.HoTen
        """,
        params,
    )


@router.post("/staff-shifts", status_code=201)
def assign_staff_shift(
    body: AssignShiftRequest,
    user: dict = Depends(require_permission("STAFF.MANAGE_BRANCH")),
):
    nv = fetch_one("SELECT MaNV, MaCN, HoTen FROM NHAN_VIEN WHERE MaNV = %s", (body.ma_nv,))
    if not nv:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhân viên")
    ensure_branch_access(user, nv["MaCN"])

    ca = fetch_one("SELECT MaCa, TenCa FROM CA_LAM WHERE MaCa = %s", (body.ma_ca,))
    if not ca:
        raise HTTPException(status_code=404, detail="Không tìm thấy ca làm")

    with get_cursor(autocommit=False) as cur:
        cur.execute("SELECT COALESCE(MAX(MaPhanCa), 0) + 1 AS NextID FROM PHAN_CA FOR UPDATE")
        ma_pc = cur.fetchone()["NextID"]
        cur.execute(
            "INSERT INTO PHAN_CA (MaPhanCa, MaNV, MaCa, NgayLam) VALUES (%s, %s, %s, %s)",
            (ma_pc, body.ma_nv, body.ma_ca, body.ngay_lam.isoformat()),
        )
        cur.execute(
            """
            INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriMoi, LyDo)
            VALUES (%s, 'PHAN_CA_NHAN_VIEN', 'PHAN_CA', %s,
                    JSON_OBJECT('MaNV', %s, 'MaCa', %s, 'NgayLam', %s),
                    'Xếp ca làm việc cho nhân viên')
            """,
            (user["MaTK"], str(ma_pc), body.ma_nv, body.ma_ca, body.ngay_lam.isoformat()),
        )
    return {
        "message": f"Đã xếp ca '{ca['TenCa']}' cho {nv['HoTen']} ngày {body.ngay_lam.isoformat()}",
        "MaPhanCa": ma_pc,
    }


@router.patch("/users/{ma_tk}/status")
def update_user_status(
    ma_tk: int,
    body: UpdateAccountStatusRequest,
    user: dict = Depends(get_current_user),
):
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Chỉ Admin mới được khóa/mở khóa tài khoản")
    if ma_tk == user["MaTK"] and body.trang_thai != "Hoạt động":
        raise HTTPException(status_code=400, detail="Không thể tự khóa tài khoản đang đăng nhập")

    target = fetch_one("SELECT MaTK, TenDangNhap, TrangThai FROM TAI_KHOAN WHERE MaTK = %s", (ma_tk,))
    if not target:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")

    with get_cursor(autocommit=False) as cur:
        cur.execute("UPDATE TAI_KHOAN SET TrangThai = %s WHERE MaTK = %s", (body.trang_thai, ma_tk))
        cur.execute(
            """
            INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriCu, GiaTriMoi, LyDo)
            VALUES (%s, 'CAP_NHAT_TRANG_THAI_TAI_KHOAN', 'TAI_KHOAN', %s,
                    JSON_OBJECT('TrangThai', %s), JSON_OBJECT('TrangThai', %s),
                    'Admin thay đổi trạng thái tài khoản RBAC')
            """,
            (user["MaTK"], str(ma_tk), target["TrangThai"], body.trang_thai),
        )
    return {"message": f"Đã cập nhật trạng thái tài khoản '{target['TenDangNhap']}' → {body.trang_thai}"}
