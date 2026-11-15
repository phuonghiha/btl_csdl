import re
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException

from ..db import fetch_all, fetch_one
from ..security import ensure_branch_access
from .booking_rules import detect_holiday_range
from .rag_engine import strip_accents

_FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|CALL|EXECUTE|PREPARE|DEALLOCATE|SET|USE|SHOW|LOCK|UNLOCK|INTO\s+OUTFILE|INTO\s+DUMPFILE|LOAD_FILE|SLEEP|BENCHMARK)\b",
    re.IGNORECASE,
)
_SENSITIVE_TABLES_PATTERN = re.compile(
    r"\b(TAI_KHOAN|TAI_KHOAN_VAI_TRO|THONG_BAO_KHACH_HANG|VAI_TRO|VAI_TRO_QUYEN|QUYEN)\b",
    re.IGNORECASE,
)


def resolve_branches_by_region(region: str) -> list[dict[str, Any]]:
    region_keywords = {
        "Miền Bắc": ("ha noi", "sa pa", "sapa", "ha long", "quang ninh", "lao cai"),
        "Miền Trung": ("da nang", "hoi an", "quang nam", "hue", "thua thien hue", "nha trang", "khanh hoa"),
        "Miền Nam": ("tp.hcm", "ho chi minh", "sai gon", "phu quoc", "kien giang", "da lat", "lam dong"),
    }
    kws = region_keywords.get(region)
    if not kws:
        return []
    branches = fetch_all("SELECT MaCN, TenCN, DiaChi, SDT FROM CHI_NHANH ORDER BY MaCN")
    matched: list[dict[str, Any]] = []
    for b in branches:
        hay = strip_accents(f"{b['TenCN']} {b.get('DiaChi', '')}".lower())
        if any(k in hay for k in kws):
            matched.append(b)
    return matched


def resolve_branch(ma_cn: int | None = None, branch_keyword: str | None = None) -> dict[str, Any] | None:
    branches = fetch_all("SELECT MaCN, TenCN, DiaChi, SDT FROM CHI_NHANH ORDER BY MaCN")
    if ma_cn is not None:
        for b in branches:
            if int(b["MaCN"]) == int(ma_cn):
                return b
    if branch_keyword:
        kw = strip_accents(branch_keyword.lower()).strip()
        for b in branches:
            hay = strip_accents(f"{b['TenCN']} {b.get('DiaChi', '')}".lower())
            if kw in hay:
                return b
        # Map tu khoa thanh pho pho bien
        city_aliases = kw.split()
        for b in branches:
            hay = strip_accents(f"{b['TenCN']} {b.get('DiaChi', '')}".lower())
            if any(len(tok) >= 3 and tok in hay for tok in city_aliases):
                return b
    return branches[0] if branches else None


def tool_search_available_rooms(
    user: dict[str, Any] | None,
    ma_cn: int | None = None,
    branch_keyword: str | None = None,
    ngay_checkin: str | None = None,
    ngay_checkout: str | None = None,
    suc_chua: int = 2,
    room_type_hint: str | None = None,
    sort_order: str = "asc",
) -> dict[str, Any]:
    """Search available rooms using sp_tim_phong_trong + exact holiday/seasonal pricing."""
    branch = resolve_branch(ma_cn=ma_cn, branch_keyword=branch_keyword)
    if not branch:
        return {"error": "Không tìm thấy chi nhánh phù hợp"}

    ci = date.fromisoformat(ngay_checkin) if ngay_checkin else (date.today() + timedelta(days=7))
    co = date.fromisoformat(ngay_checkout) if ngay_checkout else (ci + timedelta(days=2))
    if co <= ci:
        co = ci + timedelta(days=1)

    rooms = fetch_all(
        "CALL sp_tim_phong_trong(%s, %s, %s, %s)",
        (branch["MaCN"], ci.isoformat(), co.isoformat(), max(1, int(suc_chua or 1))),
    )
    if rooms:
        lp_codes = sorted({r["MaLP"] for r in rooms})
        ph = ", ".join(["%s"] * len(lp_codes))
        exact_rows = fetch_all(
            f"SELECT MaLP, fn_tinh_tien_phong_khoang_ngay(MaLP, %s, %s) AS TongTienKhoangNgay FROM LOAI_PHONG WHERE MaLP IN ({ph})",
            [ci.isoformat(), co.isoformat(), *lp_codes],
        )
        exact_map = {r["MaLP"]: float(r["TongTienKhoangNgay"]) for r in exact_rows if r.get("TongTienKhoangNgay") is not None}
        for r in rooms:
            if r["MaLP"] in exact_map:
                r["GiaTamTinhChinhXac"] = exact_map[r["MaLP"]]

    if room_type_hint:
        hint_norm = strip_accents(room_type_hint.lower())
        desc_price = sort_order == "desc"
        rooms.sort(
            key=lambda r: (
                0 if hint_norm in strip_accents(str(r.get("TenLP") or "").lower()) else 1,
                -float(r.get("GiaTamTinhChinhXac") or r.get("GiaTamTinh") or 0)
                if desc_price
                else float(r.get("GiaTamTinhChinhXac") or r.get("GiaTamTinh") or 0),
            )
        )
    elif sort_order == "desc":
        rooms.sort(key=lambda r: float(r.get("GiaTamTinhChinhXac") or r.get("GiaTamTinh") or 0), reverse=True)

    holiday_info = detect_holiday_range(ci, co)
    nights = max(1, (co - ci).days)
    hint_norm = strip_accents(room_type_hint.lower()) if room_type_hint else None
    return {
        "branch": {"MaCN": branch["MaCN"], "TenCN": branch["TenCN"], "DiaChi": branch.get("DiaChi")},
        "ngay_checkin": ci.isoformat(),
        "ngay_checkout": co.isoformat(),
        "nights": nights,
        "suc_chua": max(1, int(suc_chua or 1)),
        "room_type_hint": room_type_hint,
        "holiday_info": holiday_info,
        "total_available": len(rooms),
        "rooms": [
            {
                "MaPhong": r["MaPhong"],
                "SoPhong": r["SoPhong"],
                "MaLP": r["MaLP"],
                "TenLP": r["TenLP"],
                "SucChua": r["SucChua"],
                "MatchedTier": bool(hint_norm and hint_norm in strip_accents(str(r.get("TenLP") or "").lower())),
                "GiaMoiDem": round(float(r.get("GiaTamTinhChinhXac") or r.get("GiaTamTinh") or 0) / nights, 0),
                "TongTienKhoangNgay": float(r.get("GiaTamTinhChinhXac") or r.get("GiaTamTinh") or 0),
            }
            for r in rooms[:8]
        ],
    }


def tool_room_price_rankings(
    user: dict[str, Any] | None,
    ma_cn: int | None = None,
    branch_keyword: str | None = None,
    order: str = "desc",
    target_date: str | None = None,
) -> dict[str, Any]:
    """Return highest- or lowest-priced room tier and room numbers for each branch (or a specific branch)."""
    check_day = date.fromisoformat(target_date) if target_date else date.today()
    branch_filter = ""
    params: list[Any] = [check_day.isoformat()]
    resolved_branch = None
    if ma_cn is not None or branch_keyword:
        resolved_branch = resolve_branch(ma_cn=ma_cn, branch_keyword=branch_keyword)
        if resolved_branch:
            branch_filter = "WHERE cn.MaCN = %s"
            params.append(resolved_branch["MaCN"])

    rows = fetch_all(
        f"""
        SELECT cn.MaCN, cn.TenCN, lp.MaLP, lp.TenLP, lp.SucChua,
               COALESCE(fn_gia_phong_theo_ngay(lp.MaLP, %s), MAX(bg.GiaPhong)) AS GiaNgay,
               MIN(bg.GiaPhong) AS GiaThapNhat,
               MAX(bg.GiaPhong) AS GiaCaoNhat,
               GROUP_CONCAT(DISTINCT p.SoPhong ORDER BY p.SoPhong SEPARATOR ', ') AS DanhSachPhong,
               COUNT(DISTINCT p.MaPhong) AS SoLuongPhong
        FROM CHI_NHANH cn
        JOIN PHONG p ON p.MaCN = cn.MaCN
        JOIN LOAI_PHONG lp ON lp.MaLP = p.MaLP
        LEFT JOIN BANG_GIA bg ON bg.MaLP = lp.MaLP
        {branch_filter}
        GROUP BY cn.MaCN, cn.TenCN, lp.MaLP, lp.TenLP, lp.SucChua
        """,
        params,
    )

    by_branch: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        by_branch.setdefault(int(row["MaCN"]), []).append(row)

    descending = order != "asc"
    items: list[dict[str, Any]] = []
    for cn_id in sorted(by_branch.keys()):
        candidates = by_branch[cn_id]
        candidates.sort(
            key=lambda x: (float(x.get("GiaNgay") or 0), float(x.get("GiaCaoNhat") or 0)),
            reverse=descending,
        )
        picked = candidates[0]
        all_rooms = [s.strip() for s in str(picked.get("DanhSachPhong") or "").split(",") if s.strip()]
        items.append(
            {
                "MaCN": cn_id,
                "TenCN": picked["TenCN"],
                "MaLP": picked["MaLP"],
                "TenLP": picked["TenLP"],
                "SucChua": int(picked["SucChua"]),
                "SoLuongPhong": int(picked["SoLuongPhong"]),
                "PhongDaiDien": ", ".join(all_rooms[:4]) + ("..." if len(all_rooms) > 4 else ""),
                "GiaNgay": float(picked.get("GiaNgay") or 0),
                "GiaCaoNhat": float(picked.get("GiaCaoNhat") or 0),
                "GiaThapNhat": float(picked.get("GiaThapNhat") or 0),
            }
        )

    return {
        "order": "desc" if descending else "asc",
        "target_date": check_day.isoformat(),
        "branch_scoped": resolved_branch["TenCN"] if resolved_branch else "Tất cả chi nhánh",
        "items": items,
    }


def _estimate_voucher_discount(v: dict[str, Any], order_total: float) -> float:
    min_order = float(v["DonHangToiThieu"] or 0)
    if order_total < min_order:
        return 0.0
    val = float(v["GiaTriGiam"] or 0)
    if v["LoaiGiam"] == "Phần trăm":
        disc = order_total * val / 100.0
        max_disc = float(v["GiamToiDa"] or 0)
        if max_disc > 0:
            disc = min(disc, max_disc)
        return round(disc, 0)
    return min(val, order_total)


def tool_recommend_vouchers(
    user: dict[str, Any] | None,
    ngay_checkin: str | None = None,
    ngay_checkout: str | None = None,
    has_amusement: bool = False,
    estimated_total: float = 4000000.0,
) -> dict[str, Any]:
    """Recommend the highest-discount legal voucher combination under holiday/scope rules."""
    ci = date.fromisoformat(ngay_checkin) if ngay_checkin else (date.today() + timedelta(days=7))
    co = date.fromisoformat(ngay_checkout) if ngay_checkout else (ci + timedelta(days=2))
    holiday_info = detect_holiday_range(ci, co)
    is_hol = holiday_info["is_holiday"]

    active = fetch_all(
        """
        SELECT Code, LoaiApDung, LoaiGiam, GiaTriGiam, DonHangToiThieu, GiamToiDa, NgayKetThuc
        FROM MA_GIAM_GIA
        WHERE TrangThai = 'Hiệu lực'
          AND CURRENT_DATE() BETWEEN NgayBatDau AND NgayKetThuc
          AND SoLuongDaDung < SoLuongPhatHanh
        """
    )

    if is_hol and not has_amusement:
        return {
            "is_holiday": True,
            "holiday_names": holiday_info["holiday_names"],
            "has_amusement": False,
            "rule": "Ngày lễ khi chỉ đặt phòng khách sạn không áp dụng voucher (0 mã).",
            "recommended_codes": [],
            "estimated_savings": 0,
        }

    scored = []
    for v in active:
        if not has_amusement and v["LoaiApDung"] == "Khu vui chơi":
            continue
        disc = _estimate_voucher_discount(v, float(estimated_total or 0))
        if disc > 0:
            scored.append({**v, "uoc_tinh_giam": disc})
    scored.sort(key=lambda x: x["uoc_tinh_giam"], reverse=True)

    picked: list[dict[str, Any]] = []
    if is_hol:
        if scored:
            picked.append(scored[0])
        rule = "Ngày lễ (Khách sạn + Khu vui chơi): chọn tối đa 1 voucher (1 trong 2 loại)."
    elif has_amusement:
        best_ks = next((x for x in scored if x["LoaiApDung"] == "Khách sạn"), None)
        best_vc = next((x for x in scored if x["LoaiApDung"] == "Khu vui chơi"), None)
        if best_ks:
            picked.append(best_ks)
        if best_vc:
            picked.append(best_vc)
        rule = "Ngày thường (Khách sạn + Khu vui chơi): chọn tối đa 2 voucher (1 Khách sạn + 1 Khu vui chơi)."
    else:
        best_ks = next((x for x in scored if x["LoaiApDung"] == "Khách sạn"), None)
        if best_ks:
            picked.append(best_ks)
        rule = "Ngày thường (Chỉ đặt khách sạn): chọn tối đa 1 voucher Khách sạn."

    return {
        "is_holiday": is_hol,
        "holiday_names": holiday_info["holiday_names"],
        "has_amusement": has_amusement,
        "estimated_total": float(estimated_total),
        "rule": rule,
        "recommended": [
            {
                "Code": p["Code"],
                "LoaiApDung": p["LoaiApDung"],
                "UocTinhGiam": p["uoc_tinh_giam"],
                "DonHangToiThieu": float(p["DonHangToiThieu"]),
            }
            for p in picked
        ],
        "estimated_savings": sum(p["uoc_tinh_giam"] for p in picked),
    }


def tool_get_catalog_highlights(
    user: dict[str, Any] | None,
    ma_cn: int | None = None,
    branch_keyword: str | None = None,
) -> dict[str, Any]:
    branch = resolve_branch(ma_cn=ma_cn, branch_keyword=branch_keyword)
    if not branch:
        return {"error": "Không tìm thấy chi nhánh"}
    b_id = branch["MaCN"]
    services = fetch_all(
        """
        SELECT dcn.MaDV, dv.TenDV, dv.LoaiDV, dcn.DonGia, dcn.TrangThai
        FROM DV_CHI_NHANH dcn
        JOIN DICH_VU dv ON dv.MaDV = dcn.MaDV
        WHERE dcn.MaCN = %s AND dcn.TrangThai <> 'Tạm ngưng'
        ORDER BY dcn.DonGia
        LIMIT 12
        """,
        (b_id,),
    )
    tickets = fetch_all(
        """
        SELECT kv.TenKhu, kv.LoaiKhu, lv.MaLoaiVe, lv.TenLoaiVe, lv.DoiTuong, lv.GiaVe
        FROM LOAI_VE lv
        JOIN KHU_VUI_CHOI kv ON kv.MaKhu = lv.MaKhu
        WHERE kv.MaCN = %s
        ORDER BY lv.GiaVe
        LIMIT 12
        """,
        (b_id,),
    )
    combos = fetch_all(
        """
        SELECT gc.MaCombo, gc.TenCombo, gc.GiaGoi, lp.TenLP
        FROM GOI_COMBO gc
        JOIN LOAI_PHONG lp ON lp.MaLP = gc.MaLP
        WHERE gc.MaCN = %s
        ORDER BY gc.GiaGoi
        LIMIT 8
        """,
        (b_id,),
    )
    return {
        "branch": branch,
        "services": services,
        "tickets": tickets,
        "combos": combos,
    }


def tool_get_my_bookings_and_notifications(user: dict[str, Any] | None) -> dict[str, Any]:
    if not user:
        return {"error": "Bạn cần đăng nhập để AI tra cứu đơn đặt phòng và thông báo cá nhân."}
    if not user.get("MaKH"):
        return {"info": "Tài khoản hiện tại là nhân viên/quản trị (không gắn mã khách hàng cá nhân)."}

    bookings = fetch_all(
        """
        SELECT MaDP, MaCN, TenCN, SoPhong, TenLP, NgayCheckIn, NgayCheckOut,
               TrangThaiDatPhong, MaHD, TongTienHoaDon, TrangThaiHoaDon
        FROM vw_chi_tiet_dat_phong_day_du
        WHERE MaKH = %s
        ORDER BY MaDP DESC
        LIMIT 10
        """,
        (user["MaKH"],),
    )
    notifications = fetch_all(
        """
        SELECT MaTB, MaDP, LoaiTB, TieuDe, TrangThai, OtpCode, ThoiGianTao
        FROM THONG_BAO_KHACH_HANG
        WHERE MaKH = %s
        ORDER BY MaTB DESC
        LIMIT 10
        """,
        (user["MaKH"],),
    )
    return {
        "customer_name": user.get("TenKhachHang") or user["TenDangNhap"],
        "bookings": bookings,
        "notifications": notifications,
    }


def tool_bi_branch_analytics(
    user: dict[str, Any] | None,
    ma_cn: int | None = None,
) -> dict[str, Any]:
    """Branch-scoped BI & Audit analytics strictly restricted by RBAC permissions."""
    if not user:
        raise HTTPException(status_code=401, detail="Cần đăng nhập để xem báo cáo quản trị")

    can_bi = (
        user["is_admin"]
        or "REPORT.READ_BRANCH" in user["permissions"]
        or "BOOKING.READ_BRANCH" in user["permissions"]
    )
    if not can_bi:
        raise HTTPException(
            status_code=403,
            detail="Tài khoản Khách hàng không có quyền truy vấn số liệu BI/doanh thu nội bộ.",
        )

    if ma_cn is not None:
        ensure_branch_access(user, ma_cn)
        where_sql, params = "WHERE MaCN = %s", [ma_cn]
        dp_where, dp_params = "WHERE p.MaCN = %s", [ma_cn]
    elif user["is_admin"]:
        where_sql, params = "", []
        dp_where, dp_params = "", []
    else:
        if not user["branch_ids"]:
            return {"scope": "empty", "revenue_by_branch": [], "room_occupancy": [], "booking_status": [], "top_services": []}
        ph = ", ".join(["%s"] * len(user["branch_ids"]))
        where_sql, params = f"WHERE MaCN IN ({ph})", list(user["branch_ids"])
        dp_where, dp_params = f"WHERE p.MaCN IN ({ph})", list(user["branch_ids"])

    revenue = fetch_all(
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
    occupancy = fetch_all(
        f"SELECT * FROM vw_cong_suat_phong_chi_nhanh {where_sql} ORDER BY MaCN",
        params,
    )
    booking_status = fetch_all(
        f"""
        SELECT dp.TrangThai, COUNT(DISTINCT dp.MaDP) AS SoDon
        FROM DAT_PHONG dp
        JOIN CT_DAT_PHONG c ON c.MaDP = dp.MaDP
        JOIN PHONG p ON p.MaPhong = c.MaPhong
        {dp_where}
        GROUP BY dp.TrangThai
        """,
        dp_params,
    )
    top_services = fetch_all(
        f"""
        SELECT MaDV, TenDV, LoaiDV, SUM(TongLuot) AS TongLuot, SUM(TongDoanhThu) AS TongDoanhThu
        FROM (
            SELECT MaDV, TenDV, LoaiDV, SUM(SoLuotSuDung) AS TongLuot, SUM(TongDoanhThuDV) AS TongDoanhThu
            FROM vw_su_dung_dich_vu_chi_tiet
            {where_sql}
            GROUP BY MaDV, TenDV, LoaiDV
        ) t
        GROUP BY MaDV, TenDV, LoaiDV
        ORDER BY TongDoanhThu DESC
        LIMIT 5
        """,
        params,
    )
    recent_cancels = fetch_all(
        f"""
        SELECT dp.MaDP, p.MaCN, dp.NgayDat, dp.GhiChu
        FROM DAT_PHONG dp
        JOIN CT_DAT_PHONG c ON c.MaDP = dp.MaDP
        JOIN PHONG p ON p.MaPhong = c.MaPhong
        {dp_where + (' AND ' if dp_where else 'WHERE ')} dp.TrangThai = 'Đã hủy'
        ORDER BY dp.MaDP DESC
        LIMIT 5
        """,
        dp_params,
    )
    return {
        "scope": "all_branches" if (user["is_admin"] and ma_cn is None) else f"branches:{ma_cn or user['branch_ids']}",
        "revenue_by_branch": revenue,
        "room_occupancy": occupancy,
        "booking_status": booking_status,
        "top_services": top_services,
        "recent_cancels": recent_cancels,
    }


def validate_safe_readonly_sql(sql_query: str) -> str:
    """Strictly validate that an AI-generated query is a single read-only SELECT without sensitive tables."""
    cleaned = sql_query.strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("Câu truy vấn SQL trống")
    if ";" in cleaned:
        raise ValueError("Không cho phép nhiều câu lệnh SQL phân tách bằng ';'")
    if not re.match(r"^(SELECT|WITH)\b", cleaned, re.IGNORECASE):
        raise ValueError("Chỉ cho phép câu lệnh SELECT hoặc WITH (read-only)")
    if _FORBIDDEN_SQL_PATTERN.search(cleaned):
        raise ValueError("Phát hiện từ khóa SQL bị cấm (ghi/xóa/thay đổi cấu trúc)")
    if _SENSITIVE_TABLES_PATTERN.search(cleaned):
        raise ValueError("Không cho phép truy vấn bảng nhạy cảm (TAI_KHOAN, QUYEN, THONG_BAO_KHACH_HANG)")
    if not re.search(r"\bLIMIT\s+\d+", cleaned, re.IGNORECASE):
        cleaned = f"{cleaned} LIMIT 30"
    return cleaned


def tool_run_safe_readonly_sql(user: dict[str, Any] | None, sql_query: str) -> dict[str, Any]:
    """Execute a validated read-only analytical SELECT query (Admin only)."""
    if not user or not user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Text-to-SQL tự do chỉ dành cho tài khoản ADMIN; Quản lý chi nhánh dùng công cụ báo cáo giới hạn chi nhánh.",
        )
    try:
        safe_sql = validate_safe_readonly_sql(sql_query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    rows = fetch_all(safe_sql)
    return {
        "executed_sql": safe_sql,
        "row_count": len(rows),
        "rows": rows[:30],
    }
