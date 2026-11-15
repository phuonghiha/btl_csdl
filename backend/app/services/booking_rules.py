from datetime import date, timedelta
import secrets
from typing import Any

from fastapi import HTTPException

from ..db import call_proc_with_out, fetch_all, fetch_one, get_cursor

FIXED_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "Tết Dương lịch (01/01)",
    (4, 30): "Ngày Giải phóng miền Nam (30/04)",
    (5, 1): "Ngày Quốc tế Lao động (01/05)",
    (6, 1): "Ngày Quốc tế Thiếu nhi (01/06)",
    (9, 1): "Kỳ nghỉ Quốc khánh (01/09)",
    (9, 2): "Ngày Quốc khánh (02/09)",
    (12, 24): "Lễ Giáng sinh (24/12)",
    (12, 25): "Lễ Giáng sinh (25/12)",
}

LUNAR_HOLIDAY_NAMES: dict[str, str] = {
    "LE02": "Tết Nguyên Đán",
    "LE03": "Giỗ Tổ Hùng Vương",
}


def detect_holiday_range(ngay_checkin: date, ngay_checkout: date | None = None) -> dict[str, Any]:
    """Check whether any night/day in [ngay_checkin, ngay_checkout) falls on a holiday."""
    end_date = ngay_checkout if (ngay_checkout and ngay_checkout > ngay_checkin) else (ngay_checkin + timedelta(days=1))
    last_inclusive = end_date - timedelta(days=1)

    lunar_rows = fetch_all(
        """
        SELECT MaSuKienLe, TenSuKien, NgayBatDauDuong, NgayKetThucDuong
        FROM QUY_DOI_LE_AM_LICH
        WHERE NgayKetThucDuong >= %s AND NgayBatDauDuong <= %s
        """,
        (ngay_checkin.isoformat(), last_inclusive.isoformat()),
    )
    lunar_ranges: list[tuple[date, date, str]] = []
    for row in lunar_rows:
        s = row["NgayBatDauDuong"]
        e = row["NgayKetThucDuong"]
        if isinstance(s, str):
            s = date.fromisoformat(s)
        if isinstance(e, str):
            e = date.fromisoformat(e)
        name = row.get("TenSuKien") or LUNAR_HOLIDAY_NAMES.get(row["MaSuKienLe"], row["MaSuKienLe"])
        lunar_ranges.append((s, e, name))

    holiday_dates: list[str] = []
    holiday_names: list[str] = []
    cur_d = ngay_checkin
    while cur_d <= last_inclusive:
        matched_name = FIXED_HOLIDAYS.get((cur_d.month, cur_d.day))
        if not matched_name:
            for s, e, name in lunar_ranges:
                if s <= cur_d <= e:
                    matched_name = name
                    break
        if matched_name:
            holiday_dates.append(cur_d.isoformat())
            if matched_name not in holiday_names:
                holiday_names.append(matched_name)
        cur_d += timedelta(days=1)

    return {
        "is_holiday": len(holiday_dates) > 0,
        "holiday_dates": holiday_dates,
        "holiday_names": holiday_names,
    }


def validate_voucher_selection(
    voucher_codes: list[str],
    is_holiday: bool,
    has_hotel: bool,
    has_amusement: bool,
) -> list[dict[str, Any]]:
    """Validate selected vouchers against holiday and scope (Khách sạn / Khu vui chơi) rules."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in voucher_codes:
        code = (raw or "").strip().upper()
        if not code:
            continue
        if code in seen:
            raise HTTPException(status_code=400, detail=f"Voucher '{code}' bị chọn trùng lặp")
        seen.add(code)
        cleaned.append(code)

    if not cleaned:
        return []

    today = date.today()
    vouchers: list[dict[str, Any]] = []
    for code in cleaned:
        row = fetch_one(
            """
            SELECT MaVoucher, Code, LoaiApDung, LoaiGiam, GiaTriGiam,
                   DonHangToiThieu, GiamToiDa, SoLuongPhatHanh, SoLuongDaDung,
                   NgayBatDau, NgayKetThuc, TrangThai
            FROM MA_GIAM_GIA
            WHERE UPPER(Code) = %s
            """,
            (code,),
        )
        if not row:
            raise HTTPException(status_code=400, detail=f"Không tìm thấy mã giảm giá '{code}'")
        if row["TrangThai"] != "Hiệu lực":
            raise HTTPException(status_code=400, detail=f"Mã giảm giá '{row['Code']}' hiện không ở trạng thái Hiệu lực")
        nbd = row["NgayBatDau"]
        nkt = row["NgayKetThuc"]
        if isinstance(nbd, str):
            nbd = date.fromisoformat(nbd)
        if isinstance(nkt, str):
            nkt = date.fromisoformat(nkt)
        if today < nbd or today > nkt:
            raise HTTPException(status_code=400, detail=f"Mã giảm giá '{row['Code']}' đã hết hạn hoặc chưa đến ngày áp dụng")
        if row["SoLuongDaDung"] >= row["SoLuongPhatHanh"]:
            raise HTTPException(status_code=400, detail=f"Mã giảm giá '{row['Code']}' đã hết lượt sử dụng")
        vouchers.append(row)

    ks_vouchers = [v for v in vouchers if v["LoaiApDung"] == "Khách sạn"]
    vc_vouchers = [v for v in vouchers if v["LoaiApDung"] == "Khu vui chơi"]

    if not has_hotel and ks_vouchers:
        raise HTTPException(status_code=400, detail="Đơn không có phòng khách sạn nên không thể áp dụng voucher Khách sạn")
    if not has_amusement and vc_vouchers:
        raise HTTPException(status_code=400, detail="Đơn không có vé khu vui chơi nên không thể áp dụng voucher Khu vui chơi")

    if is_holiday:
        if has_hotel and not has_amusement:
            raise HTTPException(
                status_code=400,
                detail="Ngày lễ khi chỉ đặt phòng khách sạn không được áp dụng voucher giảm giá",
            )
        if len(vouchers) > 1:
            raise HTTPException(
                status_code=400,
                detail="Ngày lễ chỉ được chọn tối đa 1 voucher (Khách sạn hoặc Khu vui chơi)",
            )
        if not has_hotel and has_amusement and len(vc_vouchers) != len(vouchers):
            raise HTTPException(status_code=400, detail="Ngày lễ chỉ đặt khu vui chơi chỉ được chọn 1 voucher Khu vui chơi")
    else:
        if len(ks_vouchers) > 1:
            raise HTTPException(status_code=400, detail="Chỉ được chọn tối đa 1 voucher Khách sạn")
        if len(vc_vouchers) > 1:
            raise HTTPException(status_code=400, detail="Chỉ được chọn tối đa 1 voucher Khu vui chơi")
        if len(vouchers) > 2:
            raise HTTPException(status_code=400, detail="Chỉ được chọn tối đa 2 voucher (1 Khách sạn + 1 Khu vui chơi)")

    return vouchers


def record_service_order_tx(
    ma_dp: int,
    ma_cn: int,
    ma_dv: int,
    so_luong: int,
    actor_ma_tk: int,
) -> dict[str, Any]:
    """Validate and record a service order onto SU_DUNG_DV + CT_HOA_DON for a booking."""
    if so_luong <= 0:
        raise HTTPException(status_code=400, detail="Số lượng dịch vụ phải lớn hơn 0")

    dp = fetch_one(
        """
        SELECT dp.MaDP, dp.MaKH, dp.TrangThai, hd.MaHD
        FROM DAT_PHONG dp
        LEFT JOIN HOA_DON hd ON hd.MaDP = dp.MaDP
        WHERE dp.MaDP = %s
        """,
        (ma_dp,),
    )
    if not dp:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt phòng")
    if dp["TrangThai"] in ("Đã hủy", "Đã trả phòng"):
        raise HTTPException(status_code=400, detail=f"Không thể thêm dịch vụ cho đơn ở trạng thái '{dp['TrangThai']}'")

    branch_match = fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM CT_DAT_PHONG c
        JOIN PHONG p ON p.MaPhong = c.MaPhong
        WHERE c.MaDP = %s AND p.MaCN = %s
        """,
        (ma_dp, ma_cn),
    )
    if not branch_match or branch_match["cnt"] == 0:
        raise HTTPException(status_code=400, detail="Đơn đặt phòng không có phòng tại chi nhánh này")

    svc = fetch_one(
        """
        SELECT dcn.DonGia, dcn.TrangThai, dv.TenDV
        FROM DV_CHI_NHANH dcn
        JOIN DICH_VU dv ON dv.MaDV = dcn.MaDV
        WHERE dcn.MaCN = %s AND dcn.MaDV = %s
        """,
        (ma_cn, ma_dv),
    )
    if not svc:
        raise HTTPException(status_code=404, detail="Chi nhánh không cung cấp dịch vụ này")
    if svc["TrangThai"] != "Đang cung cấp":
        raise HTTPException(status_code=400, detail=f"Dịch vụ '{svc['TenDV']}' hiện đang tạm ngưng tại chi nhánh")
    if not dp["MaHD"]:
        raise HTTPException(status_code=400, detail="Đơn đặt phòng chưa có hóa đơn để ghi nhận dịch vụ")

    if dp["TrangThai"] in ("Đã xác nhận", "Đang lưu trú"):
        out = call_proc_with_out(
            "sp_ghi_nhan_su_dung_dv",
            (ma_dp, ma_cn, ma_dv, so_luong, actor_ma_tk),
            ["MaSD"],
        )
        ma_sd = out.get("MaSD")
    else:
        # Chờ xác nhận: khách tự đặt trước hoặc xác nhận đề xuất dịch vụ để thanh toán cùng hóa đơn
        with get_cursor(autocommit=False) as cur:
            cur.execute("SELECT COALESCE(MAX(MaSD), 0) + 1 AS NextSD FROM SU_DUNG_DV FOR UPDATE")
            ma_sd = cur.fetchone()["NextSD"]
            cur.execute("SELECT COALESCE(MAX(MaCTHD), 0) + 1 AS NextCT FROM CT_HOA_DON FOR UPDATE")
            ma_cthd = cur.fetchone()["NextCT"]
            cur.execute(
                """
                INSERT INTO SU_DUNG_DV (MaSD, MaDP, MaCN, MaDV, ThoiGianSD, SoLuong, DonGiaTaiThoiDiem)
                VALUES (%s, %s, %s, %s, NOW(), %s, %s)
                """,
                (ma_sd, ma_dp, ma_cn, ma_dv, so_luong, svc["DonGia"]),
            )
            cur.execute(
                """
                INSERT INTO CT_HOA_DON (MaCTHD, MaHD, LoaiKhoanThu, MoTa, SoLuong, DonGia)
                VALUES (%s, %s, 'Dịch vụ', %s, %s, %s)
                """,
                (ma_cthd, dp["MaHD"], f"{svc['TenDV']} (x{so_luong})", so_luong, svc["DonGia"]),
            )
            cur.execute(
                """
                INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriMoi, LyDo)
                VALUES (%s, 'GHI_NHAN_DICH_VU', 'SU_DUNG_DV', %s,
                        JSON_OBJECT('MaDP', %s, 'MaDV', %s, 'SoLuong', %s, 'DonGia', %s),
                        'Ghi nhận đặt trước dịch vụ cho đơn đặt phòng')
                """,
                (actor_ma_tk, str(ma_sd), ma_dp, ma_dv, so_luong, float(svc["DonGia"])),
            )

    return {
        "MaSD": ma_sd,
        "MaHD": dp["MaHD"],
        "MaDP": ma_dp,
        "MaCN": ma_cn,
        "MaDV": ma_dv,
        "TenDV": svc["TenDV"],
        "SoLuong": so_luong,
        "DonGia": float(svc["DonGia"]),
        "ThanhTien": float(svc["DonGia"]) * so_luong,
    }


def issue_tickets_tx(
    ma_dp: int,
    ma_kh: int,
    ma_hd: int | None,
    ma_loai_ve: int,
    ngay_su_dung: date,
    so_luong: int,
    actor_ma_tk: int,
    expected_ma_cn: int | None = None,
) -> list[dict[str, Any]]:
    """Issue electronic QR tickets for a booking and append them to CT_HOA_DON."""
    loai_ve = fetch_one(
        """
        SELECT lv.MaLoaiVe, lv.TenLoaiVe, lv.GiaVe, kv.MaCN, kv.TenKhu
        FROM LOAI_VE lv
        JOIN KHU_VUI_CHOI kv ON kv.MaKhu = lv.MaKhu
        WHERE lv.MaLoaiVe = %s
        """,
        (ma_loai_ve,),
    )
    if not loai_ve:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy loại vé #{ma_loai_ve}")
    if expected_ma_cn is not None and int(loai_ve["MaCN"]) != int(expected_ma_cn):
        raise HTTPException(status_code=400, detail="Loại vé không thuộc cùng chi nhánh với đơn đặt phòng")

    issued: list[dict[str, Any]] = []
    with get_cursor(autocommit=False) as cur:
        cur.execute("SELECT COALESCE(MAX(MaVe), 0) AS MaxVe FROM VE_DIEN_TU FOR UPDATE")
        next_ve = cur.fetchone()["MaxVe"] + 1

        for _ in range(so_luong):
            ma_qr = f"QR-LIVE-{ma_dp}-{next_ve}-{secrets.token_hex(2).upper()}"
            cur.execute(
                """
                INSERT INTO VE_DIEN_TU (MaVe, MaDP, MaKH, MaLoaiVe, MaQR, NgaySuDung, GiaTien, TrangThai, ThoiGianQuet)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'Chưa sử dụng', NULL)
                """,
                (
                    next_ve,
                    ma_dp,
                    ma_kh,
                    ma_loai_ve,
                    ma_qr,
                    ngay_su_dung.isoformat(),
                    loai_ve["GiaVe"],
                ),
            )
            issued.append({"MaVe": next_ve, "MaQR": ma_qr, "TenLoaiVe": loai_ve["TenLoaiVe"], "GiaVe": float(loai_ve["GiaVe"])})
            next_ve += 1

        if ma_hd is not None:
            cur.execute("SELECT COALESCE(MAX(MaCTHD), 0) + 1 AS NextCT FROM CT_HOA_DON FOR UPDATE")
            next_ct = cur.fetchone()["NextCT"]
            cur.execute(
                """
                INSERT INTO CT_HOA_DON (MaCTHD, MaHD, LoaiKhoanThu, MoTa, SoLuong, DonGia)
                VALUES (%s, %s, 'Vé vui chơi', %s, %s, %s)
                """,
                (
                    next_ct,
                    ma_hd,
                    f"{loai_ve['TenLoaiVe']} - {loai_ve['TenKhu']}",
                    so_luong,
                    loai_ve["GiaVe"],
                ),
            )

        cur.execute(
            """
            INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriMoi, LyDo)
            VALUES (%s, 'PHAT_HANH_VE_QR', 'VE_DIEN_TU', %s,
                    JSON_OBJECT('MaDP', %s, 'MaLoaiVe', %s, 'SoLuong', %s),
                    'Phát hành vé điện tử cho đơn đặt phòng')
            """,
            (actor_ma_tk, str(issued[0]["MaVe"]), ma_dp, ma_loai_ve, so_luong),
        )
    return issued


def apply_vouchers_tx(ma_hd: int, vouchers: list[dict[str, Any]], actor_ma_tk: int) -> list[dict[str, Any]]:
    """Apply validated vouchers sequentially via sp_ap_ma_giam_gia."""
    applied: list[dict[str, Any]] = []
    for v in vouchers:
        res = call_proc_with_out(
            "sp_ap_ma_giam_gia",
            (ma_hd, v["Code"], actor_ma_tk),
            ["SoTienGiam"],
        )
        applied.append(
            {
                "Code": v["Code"],
                "LoaiApDung": v["LoaiApDung"],
                "SoTienGiam": float(res.get("SoTienGiam") or 0),
            }
        )
    return applied
