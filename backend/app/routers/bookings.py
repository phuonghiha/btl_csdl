from datetime import date
import secrets
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import call_proc_with_out, fetch_all, fetch_one, get_cursor
from ..security import ensure_branch_access, get_current_user, require_permission
from ..services.booking_rules import (
    apply_vouchers_tx,
    detect_holiday_range,
    issue_tickets_tx,
    validate_voucher_selection,
)
from .finance import build_transfer_qr_info

router = APIRouter(prefix="/api/bookings", tags=["Đặt phòng & Lưu trú"])


class BookingTicketItem(BaseModel):
    ma_loai_ve: int
    so_luong: int = Field(default=1, ge=1, le=20)
    ngay_su_dung: date | None = None


class CreateBookingRequest(BaseModel):
    ma_kh: int | None = None
    ma_phong: int
    ngay_checkin: date
    ngay_checkout: date
    ma_combo: int | None = None
    ghi_chu: str | None = Field(default=None, max_length=1000)
    ticket_items: list[BookingTicketItem] = Field(default_factory=list)
    voucher_codes: list[str] = Field(default_factory=list)


class SendCancelOtpRequest(BaseModel):
    ly_do: str | None = Field(default=None, max_length=500)


class CancelBookingRequest(BaseModel):
    ly_do: str = Field(..., min_length=3, max_length=500)
    otp_code: str | None = Field(default=None, max_length=12)


def _get_booking_branch_and_owner(ma_dp: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT dp.MaDP, dp.MaKH, dp.TrangThai, MIN(p.MaCN) AS MaCN
        FROM DAT_PHONG dp
        LEFT JOIN CT_DAT_PHONG c ON c.MaDP = dp.MaDP
        LEFT JOIN PHONG p ON p.MaPhong = c.MaPhong
        WHERE dp.MaDP = %s
        GROUP BY dp.MaDP, dp.MaKH, dp.TrangThai
        """,
        (ma_dp,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt phòng")
    return row


@router.get("/availability")
def search_availability(
    ma_cn: int = Query(..., ge=1),
    ngay_checkin: date = Query(...),
    ngay_checkout: date = Query(...),
    suc_chua: int = Query(default=1, ge=1, le=20),
):
    if ngay_checkout <= ngay_checkin:
        raise HTTPException(status_code=400, detail="Ngày trả phòng phải sau ngày nhận phòng")

    with get_cursor() as cur:
        cur.execute(
            "CALL sp_tim_phong_trong(%s, %s, %s, %s)",
            (ma_cn, ngay_checkin.isoformat(), ngay_checkout.isoformat(), suc_chua),
        )
        rooms = list(cur.fetchall())

    # Bo sung gia chinh xac theo tung dem (bao gom giao thoa le am lich / mua)
    if rooms:
        lp_codes = sorted({r["MaLP"] for r in rooms})
        placeholders = ", ".join(["%s"] * len(lp_codes))
        exact_rows = fetch_all(
            f"""
            SELECT MaLP, fn_tinh_tien_phong_khoang_ngay(MaLP, %s, %s) AS TongTienKhoangNgay
            FROM LOAI_PHONG
            WHERE MaLP IN ({placeholders})
            """,
            [ngay_checkin.isoformat(), ngay_checkout.isoformat(), *lp_codes],
        )
        exact_map = {r["MaLP"]: r["TongTienKhoangNgay"] for r in exact_rows}
        for room in rooms:
            if room["MaLP"] in exact_map and exact_map[room["MaLP"]] is not None:
                room["GiaTamTinhChinhXac"] = exact_map[room["MaLP"]]
    return rooms


@router.get("")
def list_bookings(
    ma_cn: int | None = Query(default=None),
    trang_thai: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    can_branch = user["is_admin"] or "BOOKING.READ_BRANCH" in user["permissions"]
    can_self = "BOOKING.READ_SELF" in user["permissions"]

    if not can_branch and not can_self:
        raise HTTPException(status_code=403, detail="Không có quyền xem danh sách đặt phòng")

    clauses = []
    params: list[Any] = []

    if can_branch:
        if ma_cn is not None:
            ensure_branch_access(user, ma_cn)
            clauses.append("MaCN = %s")
            params.append(ma_cn)
        elif not user["is_admin"]:
            if not user["branch_ids"]:
                return []
            ph = ", ".join(["%s"] * len(user["branch_ids"]))
            clauses.append(f"MaCN IN ({ph})")
            params.extend(user["branch_ids"])
    else:
        if user["MaKH"] is None:
            return []
        clauses.append("MaKH = %s")
        params.append(user["MaKH"])
        if ma_cn is not None:
            clauses.append("MaCN = %s")
            params.append(ma_cn)

    if trang_thai:
        clauses.append("TrangThaiDatPhong = %s")
        params.append(trang_thai)

    if q and q.strip():
        kw = f"%{q.strip()}%"
        clauses.append(
            "(TenKhachHang LIKE %s OR SdtKhachHang LIKE %s OR SoPhong LIKE %s OR CAST(MaDP AS CHAR) = %s)"
        )
        params.extend([kw, kw, kw, q.strip()])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    return fetch_all(
        f"""
        SELECT * FROM vw_chi_tiet_dat_phong_day_du
        {where_sql}
        ORDER BY MaDP DESC, MaCTDP
        LIMIT %s
        """,
        params,
    )


@router.get("/holiday-status")
def get_holiday_status(
    ngay_checkin: date = Query(...),
    ngay_checkout: date | None = Query(default=None),
):
    return detect_holiday_range(ngay_checkin, ngay_checkout)


@router.get("/{ma_dp}")
def get_booking_detail(ma_dp: int, user: dict = Depends(get_current_user)):
    meta = _get_booking_branch_and_owner(ma_dp)
    can_branch = user["is_admin"] or "BOOKING.READ_BRANCH" in user["permissions"]
    if can_branch:
        if meta["MaCN"] is not None:
            ensure_branch_access(user, meta["MaCN"])
    elif "BOOKING.READ_SELF" in user["permissions"] and user["MaKH"] == meta["MaKH"]:
        pass
    else:
        raise HTTPException(status_code=403, detail="Không có quyền xem đơn đặt phòng này")

    rows = fetch_all("SELECT * FROM vw_chi_tiet_dat_phong_day_du WHERE MaDP = %s", (ma_dp,))
    services = fetch_all(
        """
        SELECT sd.*, dv.TenDV, dv.LoaiDV
        FROM SU_DUNG_DV sd
        JOIN DICH_VU dv ON dv.MaDV = sd.MaDV
        WHERE sd.MaDP = %s
        ORDER BY sd.ThoiGianSD DESC
        """,
        (ma_dp,),
    )
    tickets = fetch_all(
        """
        SELECT ve.*, lv.TenLoaiVe, kv.TenKhu
        FROM VE_DIEN_TU ve
        JOIN LOAI_VE lv ON lv.MaLoaiVe = ve.MaLoaiVe
        JOIN KHU_VUI_CHOI kv ON kv.MaKhu = lv.MaKhu
        WHERE ve.MaDP = %s
        """,
        (ma_dp,),
    )
    return {"rooms": rows, "services": services, "tickets": tickets}


@router.post("", status_code=201)
def create_booking(body: CreateBookingRequest, user: dict = Depends(require_permission("BOOKING.CREATE"))):
    # Khach hang chi duoc dat cho chinh minh; nhan vien/admin co the chi dinh ma_kh
    if user["MaKH"] is not None and not user["is_admin"]:
        ma_kh = user["MaKH"]
    elif body.ma_kh is not None:
        ma_kh = body.ma_kh
    else:
        raise HTTPException(status_code=400, detail="Cần cung cấp mã khách hàng (ma_kh)")

    if body.ngay_checkout <= body.ngay_checkin:
        raise HTTPException(status_code=400, detail="Ngày trả phòng phải sau ngày nhận phòng")

    room = fetch_one("SELECT MaPhong, MaCN FROM PHONG WHERE MaPhong = %s", (body.ma_phong,))
    if not room:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng được chọn")

    for t_item in body.ticket_items:
        lv = fetch_one(
            """
            SELECT lv.MaLoaiVe, kv.MaCN
            FROM LOAI_VE lv
            JOIN KHU_VUI_CHOI kv ON kv.MaKhu = lv.MaKhu
            WHERE lv.MaLoaiVe = %s
            """,
            (t_item.ma_loai_ve,),
        )
        if not lv:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy loại vé #{t_item.ma_loai_ve}")
        if int(lv["MaCN"]) != int(room["MaCN"]):
            raise HTTPException(status_code=400, detail="Vé khu vui chơi phải thuộc cùng chi nhánh với phòng đặt")

    holiday_info = detect_holiday_range(body.ngay_checkin, body.ngay_checkout)
    has_amusement = len(body.ticket_items) > 0
    validated_vouchers = validate_voucher_selection(
        body.voucher_codes,
        is_holiday=holiday_info["is_holiday"],
        has_hotel=True,
        has_amusement=has_amusement,
    )

    ghi_chu_final = body.ghi_chu
    if body.ma_combo is not None:
        combo = fetch_one(
            "SELECT MaCombo, TenCombo, GiaGoi FROM GOI_COMBO WHERE MaCombo = %s",
            (body.ma_combo,),
        )
        if not combo:
            raise HTTPException(status_code=404, detail="Không tìm thấy gói Combo")
        combo_note = f"[Combo #{combo['MaCombo']}: {combo['TenCombo']} - {int(combo['GiaGoi']):,}đ]"
        ghi_chu_final = f"{combo_note} {body.ghi_chu}".strip() if body.ghi_chu else combo_note

    out = call_proc_with_out(
        "sp_tao_dat_phong",
        (
            ma_kh,
            body.ma_phong,
            body.ngay_checkin.isoformat(),
            body.ngay_checkout.isoformat(),
            ghi_chu_final,
            user["MaTK"],
        ),
        ["MaDP", "MaHD"],
    )

    ma_dp = out.get("MaDP")
    ma_hd = out.get("MaHD")
    issued_tickets = []
    for t_item in body.ticket_items:
        issued_tickets.extend(
            issue_tickets_tx(
                ma_dp=ma_dp,
                ma_kh=ma_kh,
                ma_hd=ma_hd,
                ma_loai_ve=t_item.ma_loai_ve,
                ngay_su_dung=t_item.ngay_su_dung or body.ngay_checkin,
                so_luong=t_item.so_luong,
                actor_ma_tk=user["MaTK"],
                expected_ma_cn=room["MaCN"],
            )
        )

    applied_vouchers = []
    if validated_vouchers and ma_hd:
        applied_vouchers = apply_vouchers_tx(ma_hd, validated_vouchers, user["MaTK"])

    payment_qr = build_transfer_qr_info(ma_hd) if ma_hd else None
    return {
        "message": "Tạo đặt phòng thành công",
        "MaDP": ma_dp,
        "MaHD": ma_hd,
        "is_holiday": holiday_info["is_holiday"],
        "holiday_names": holiday_info["holiday_names"],
        "issued_tickets_count": len(issued_tickets),
        "applied_vouchers": applied_vouchers,
        "payment_qr": payment_qr,
    }


@router.post("/{ma_dp}/confirm")
def confirm_booking(ma_dp: int, user: dict = Depends(require_permission("BOOKING.CONFIRM"))):
    meta = _get_booking_branch_and_owner(ma_dp)
    if meta["MaCN"] is not None:
        ensure_branch_access(user, meta["MaCN"])
    with get_cursor() as cur:
        cur.execute("CALL sp_xac_nhan_dat_phong(%s, %s)", (ma_dp, user["MaTK"]))
    return {"message": "Đã xác nhận đặt phòng", "MaDP": ma_dp}


@router.post("/{ma_dp}/check-in")
def checkin_booking(ma_dp: int, user: dict = Depends(require_permission("BOOKING.CHECKIN_OUT"))):
    meta = _get_booking_branch_and_owner(ma_dp)
    if meta["MaCN"] is not None:
        ensure_branch_access(user, meta["MaCN"])
    with get_cursor() as cur:
        cur.execute("CALL sp_checkin_dat_phong(%s, %s)", (ma_dp, user["MaTK"]))
    return {"message": "Check-in thành công", "MaDP": ma_dp}


@router.post("/{ma_dp}/check-out")
def checkout_booking(ma_dp: int, user: dict = Depends(require_permission("BOOKING.CHECKIN_OUT"))):
    meta = _get_booking_branch_and_owner(ma_dp)
    if meta["MaCN"] is not None:
        ensure_branch_access(user, meta["MaCN"])
    with get_cursor() as cur:
        cur.execute("CALL sp_checkout_dat_phong(%s, %s)", (ma_dp, user["MaTK"]))
    return {"message": "Check-out thành công", "MaDP": ma_dp}


@router.post("/{ma_dp}/cancel-otp")
def send_cancel_otp(
    ma_dp: int,
    body: SendCancelOtpRequest | None = None,
    user: dict = Depends(get_current_user),
):
    meta = _get_booking_branch_and_owner(ma_dp)
    is_staff = user["is_admin"] or "BOOKING.CONFIRM" in user["permissions"]
    if not is_staff:
        raise HTTPException(status_code=403, detail="Chỉ Admin hoặc Lễ tân mới được gửi OTP hủy đơn")
    if meta["MaCN"] is not None:
        ensure_branch_access(user, meta["MaCN"])

    dp = fetch_one("SELECT MaDP, MaKH, TrangThai FROM DAT_PHONG WHERE MaDP = %s", (ma_dp,))
    if not dp:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt phòng")
    if dp["TrangThai"] not in ("Chờ xác nhận", "Đã xác nhận"):
        raise HTTPException(
            status_code=400,
            detail=f"Chỉ có thể gửi OTP hủy cho đơn ở trạng thái Chờ xác nhận hoặc Đã xác nhận (hiện tại: '{dp['TrangThai']}')",
        )

    otp_code = f"{secrets.randbelow(1000000):06d}"
    reason = (body.ly_do.strip() if body and body.ly_do else "Yêu cầu hủy đơn từ quầy lễ tân / quản trị")
    title = f"Mã OTP xác nhận hủy đơn #{ma_dp}"
    content = (
        f"Nhân viên/Admin đã gửi yêu cầu hủy đơn đặt phòng #{ma_dp}. "
        f"Lý do: {reason}. Mã OTP xác thực của bạn là: {otp_code} (hiệu lực 10 phút). "
        f"Chỉ cung cấp mã này cho lễ tân nếu bạn đồng ý hủy đơn."
    )

    with get_cursor(autocommit=False) as cur:
        cur.execute(
            """
            UPDATE THONG_BAO_KHACH_HANG
            SET TrangThai = 'Hết hạn'
            WHERE MaDP = %s AND LoaiTB = 'CANCEL_OTP' AND TrangThai = 'Chờ xác nhận'
            """,
            (ma_dp,),
        )
        cur.execute(
            """
            INSERT INTO THONG_BAO_KHACH_HANG
                (MaKH, MaDP, LoaiTB, TieuDe, NoiDung, OtpCode, DuLieuJson, TrangThai, NguoiGuiMaTK, HetHanLuc)
            VALUES
                (%s, %s, 'CANCEL_OTP', %s, %s, %s, JSON_OBJECT('ly_do', %s), 'Chờ xác nhận', %s, DATE_ADD(NOW(), INTERVAL 10 MINUTE))
            """,
            (dp["MaKH"], ma_dp, title, content, otp_code, reason, user["MaTK"]),
        )
        ma_tb = cur.lastrowid

    return {
        "message": "Đã gửi mã OTP xác nhận hủy đơn đến tài khoản khách hàng",
        "MaDP": ma_dp,
        "MaTB": ma_tb,
        "expires_in_seconds": 600,
    }


@router.post("/{ma_dp}/cancel")
def cancel_booking(ma_dp: int, body: CancelBookingRequest, user: dict = Depends(get_current_user)):
    meta = _get_booking_branch_and_owner(ma_dp)
    is_staff = user["is_admin"] or "BOOKING.CONFIRM" in user["permissions"]
    is_owner = "BOOKING.CANCEL_SELF" in user["permissions"] and user["MaKH"] == meta["MaKH"]

    matched_tb_id = None
    if is_staff:
        if meta["MaCN"] is not None:
            ensure_branch_access(user, meta["MaCN"])
        otp_input = (body.otp_code or "").strip()
        if not otp_input:
            raise HTTPException(
                status_code=400,
                detail="Cần nhập mã OTP xác thực từ thông báo trên tài khoản khách hàng để hủy đơn",
            )
        otp_row = fetch_one(
            """
            SELECT MaTB, OtpCode
            FROM THONG_BAO_KHACH_HANG
            WHERE MaDP = %s
              AND LoaiTB = 'CANCEL_OTP'
              AND TrangThai = 'Chờ xác nhận'
              AND (HetHanLuc IS NULL OR HetHanLuc >= NOW())
            ORDER BY MaTB DESC
            LIMIT 1
            """,
            (ma_dp,),
        )
        if not otp_row:
            raise HTTPException(
                status_code=400,
                detail="Chưa có mã OTP hợp lệ hoặc mã OTP đã hết hạn/bị từ chối. Vui lòng gửi lại OTP cho khách.",
            )
        if otp_row["OtpCode"] != otp_input:
            raise HTTPException(status_code=400, detail="Mã OTP xác thực không chính xác")
        matched_tb_id = otp_row["MaTB"]
    elif not is_owner:
        raise HTTPException(status_code=403, detail="Bạn không có quyền hủy đặt phòng này")

    with get_cursor() as cur:
        cur.execute("CALL sp_huy_dat_phong(%s, %s, %s)", (ma_dp, body.ly_do.strip(), user["MaTK"]))
        if matched_tb_id is not None:
            cur.execute(
                """
                UPDATE THONG_BAO_KHACH_HANG
                SET TrangThai = 'Đã xác nhận', ThoiGianPhanHoi = NOW()
                WHERE MaTB = %s
                """,
                (matched_tb_id,),
            )
    return {"message": "Đã hủy đặt phòng", "MaDP": ma_dp}
