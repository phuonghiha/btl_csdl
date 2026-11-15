from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import call_proc_with_out, fetch_all, fetch_one, get_cursor
from ..security import ensure_branch_access, get_current_user, require_permission
from ..services.booking_rules import (
    apply_vouchers_tx,
    detect_holiday_range,
    issue_tickets_tx,
    record_service_order_tx,
    validate_voucher_selection,
)
from .finance import build_transfer_qr_info

router = APIRouter(prefix="/api/operations", tags=["Vận hành lễ tân & Khu vui chơi"])


class RecordServiceRequest(BaseModel):
    ma_dp: int
    ma_cn: int
    ma_dv: int
    so_luong: int = Field(..., ge=1, le=100)


class ScanTicketRequest(BaseModel):
    ma_qr: str = Field(..., min_length=3, max_length=120)
    ma_cn: int


class UpdateRoomStatusRequest(BaseModel):
    trang_thai: str = Field(..., pattern="^(Trống|Đang sử dụng|Đã sẵn sàng|Bảo trì)$")


class CreateCustomerRequest(BaseModel):
    ho_ten: str = Field(..., min_length=2, max_length=160)
    cccd: str = Field(..., min_length=9, max_length=25)
    sdt: str = Field(..., min_length=8, max_length=20)
    email: str | None = Field(default=None, max_length=160)
    dia_chi: str | None = Field(default=None, max_length=300)


class IssueTicketRequest(BaseModel):
    ma_dp: int
    ma_loai_ve: int
    ngay_su_dung: date
    so_luong: int = Field(default=1, ge=1, le=20)
    voucher_code: str | None = Field(default=None, max_length=60)


class ServiceOrderRequest(BaseModel):
    ma_dp: int
    ma_cn: int
    ma_dv: int
    so_luong: int = Field(default=1, ge=1, le=100)
    ghi_chu: str | None = Field(default=None, max_length=300)


class UpdateBranchServiceRequest(BaseModel):
    don_gia: Decimal = Field(..., ge=0)
    trang_thai: str = Field(..., pattern="^(Đang cung cấp|Còn phục vụ|Tạm ngưng)$")


@router.get("/rooms")
def list_rooms(
    ma_cn: int | None = Query(default=None),
    trang_thai: str | None = Query(default=None),
    user: dict = Depends(require_permission("ROOM.READ_BRANCH")),
):
    clauses = []
    params: list[Any] = []
    if ma_cn is not None:
        ensure_branch_access(user, ma_cn)
        clauses.append("p.MaCN = %s")
        params.append(ma_cn)
    elif not user["is_admin"]:
        if not user["branch_ids"]:
            return []
        ph = ", ".join(["%s"] * len(user["branch_ids"]))
        clauses.append(f"p.MaCN IN ({ph})")
        params.extend(user["branch_ids"])

    if trang_thai:
        clauses.append("p.TrangThai = %s")
        params.append(trang_thai)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(
        f"""
        SELECT p.MaPhong, p.MaCN, cn.TenCN, p.MaLP, lp.TenLP, lp.SucChua,
               p.SoPhong, p.Tang, p.TrangThai
        FROM PHONG p
        JOIN CHI_NHANH cn ON cn.MaCN = p.MaCN
        JOIN LOAI_PHONG lp ON lp.MaLP = p.MaLP
        {where_sql}
        ORDER BY p.MaCN, p.Tang, p.SoPhong
        """,
        params,
    )


@router.patch("/rooms/{ma_phong}/status")
def update_room_status(
    ma_phong: int,
    body: UpdateRoomStatusRequest,
    user: dict = Depends(require_permission("ROOM.MANAGE_BRANCH")),
):
    room = fetch_one("SELECT MaPhong, MaCN, TrangThai FROM PHONG WHERE MaPhong = %s", (ma_phong,))
    if not room:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng")
    ensure_branch_access(user, room["MaCN"])

    with get_cursor() as cur:
        cur.execute("UPDATE PHONG SET TrangThai = %s WHERE MaPhong = %s", (body.trang_thai, ma_phong))
        cur.execute(
            """
            INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriCu, GiaTriMoi, LyDo)
            VALUES (%s, 'CAP_NHAT_TRANG_THAI_PHONG', 'PHONG', %s,
                    JSON_OBJECT('TrangThai', %s), JSON_OBJECT('TrangThai', %s),
                    'Cap nhat trang thai van hanh phong')
            """,
            (user["MaTK"], str(ma_phong), room["TrangThai"], body.trang_thai),
        )
    return {"message": "Đã cập nhật trạng thái phòng", "MaPhong": ma_phong, "TrangThai": body.trang_thai}


@router.post("/service-usages", status_code=201)
def record_service_usage(
    body: RecordServiceRequest,
    user: dict = Depends(require_permission("SERVICE.RECORD_USE")),
):
    ensure_branch_access(user, body.ma_cn)
    out = call_proc_with_out(
        "sp_ghi_nhan_su_dung_dv",
        (body.ma_dp, body.ma_cn, body.ma_dv, body.so_luong, user["MaTK"]),
        ["MaSD"],
    )
    return {"message": "Đã ghi nhận sử dụng dịch vụ", "MaSD": out.get("MaSD")}


@router.get("/tickets")
def list_tickets(
    ma_cn: int | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    can_staff = user["is_admin"] or "SERVICE.READ_BRANCH" in user["permissions"]
    clauses = []
    params: list[Any] = []

    if can_staff:
        if ma_cn is not None:
            ensure_branch_access(user, ma_cn)
            clauses.append("kv.MaCN = %s")
            params.append(ma_cn)
        elif not user["is_admin"]:
            if not user["branch_ids"]:
                return []
            ph = ", ".join(["%s"] * len(user["branch_ids"]))
            clauses.append(f"kv.MaCN IN ({ph})")
            params.extend(user["branch_ids"])
    elif user["MaKH"] is not None:
        clauses.append("ve.MaKH = %s")
        params.append(user["MaKH"])
        if ma_cn is not None:
            clauses.append("kv.MaCN = %s")
            params.append(ma_cn)
    else:
        return []

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return fetch_all(
        f"""
        SELECT ve.*, kh.HoTen AS TenKhachHang, lv.TenLoaiVe, lv.DoiTuong,
               kv.MaKhu, kv.TenKhu, kv.MaCN, cn.TenCN
        FROM VE_DIEN_TU ve
        JOIN KHACH_HANG kh ON kh.MaKH = ve.MaKH
        JOIN LOAI_VE lv ON lv.MaLoaiVe = ve.MaLoaiVe
        JOIN KHU_VUI_CHOI kv ON kv.MaKhu = lv.MaKhu
        JOIN CHI_NHANH cn ON cn.MaCN = kv.MaCN
        {where_sql}
        ORDER BY ve.MaVe DESC
        """,
        params,
    )


@router.post("/tickets/scan")
def scan_ticket(
    body: ScanTicketRequest,
    user: dict = Depends(require_permission("SERVICE.RECORD_USE")),
):
    ensure_branch_access(user, body.ma_cn)
    with get_cursor() as cur:
        cur.execute("CALL sp_quet_ve_dien_tu(%s, %s, %s)", (body.ma_qr.strip(), body.ma_cn, user["MaTK"]))
    ticket = fetch_one(
        """
        SELECT ve.*, kh.HoTen AS TenKhachHang, lv.TenLoaiVe, kv.TenKhu
        FROM VE_DIEN_TU ve
        JOIN KHACH_HANG kh ON kh.MaKH = ve.MaKH
        JOIN LOAI_VE lv ON lv.MaLoaiVe = ve.MaLoaiVe
        JOIN KHU_VUI_CHOI kv ON kv.MaKhu = lv.MaKhu
        WHERE ve.MaQR = %s
        """,
        (body.ma_qr.strip(),),
    )
    return {"message": "Soát vé thành công", "ticket": ticket}


@router.get("/customers")
def search_customers(
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    if not (
        user["is_admin"]
        or "BOOKING.READ_BRANCH" in user["permissions"]
        or "BOOKING.CONFIRM" in user["permissions"]
    ):
        raise HTTPException(status_code=403, detail="Chỉ nhân viên mới được tra cứu danh sách khách hàng")

    kw = f"%{q.strip()}%"
    return fetch_all(
        """
        SELECT MaKH, HoTen, CCCD, SDT, Email, DiaChi
        FROM KHACH_HANG
        WHERE (%s = '' OR HoTen LIKE %s OR SDT LIKE %s OR CCCD LIKE %s OR CAST(MaKH AS CHAR) = %s)
        ORDER BY MaKH DESC
        LIMIT %s
        """,
        (q.strip(), kw, kw, kw, q.strip(), limit),
    )


@router.post("/customers", status_code=201)
def create_walkin_customer(
    body: CreateCustomerRequest,
    user: dict = Depends(require_permission("BOOKING.CONFIRM")),
):
    existing = fetch_one("SELECT MaKH, HoTen, CCCD, SDT FROM KHACH_HANG WHERE CCCD = %s", (body.cccd.strip(),))
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"CCCD đã tồn tại cho khách hàng #{existing['MaKH']} ({existing['HoTen']})",
        )

    with get_cursor(autocommit=False) as cur:
        cur.execute("SELECT COALESCE(MAX(MaKH), 0) + 1 AS NextID FROM KHACH_HANG FOR UPDATE")
        ma_kh = cur.fetchone()["NextID"]
        cur.execute(
            """
            INSERT INTO KHACH_HANG (MaKH, HoTen, CCCD, SDT, Email, DiaChi)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (ma_kh, body.ho_ten.strip(), body.cccd.strip(), body.sdt.strip(), body.email, body.dia_chi),
        )
        cur.execute(
            """
            INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriMoi, LyDo)
            VALUES (%s, 'TAO_KHACH_HANG_TAI_QUAY', 'KHACH_HANG', %s,
                    JSON_OBJECT('HoTen', %s, 'SDT', %s), 'Lễ tân tạo hồ sơ khách hàng trực tiếp')
            """,
            (user["MaTK"], str(ma_kh), body.ho_ten.strip(), body.sdt.strip()),
        )
    return {"message": "Đã tạo hồ sơ khách hàng", "MaKH": ma_kh, "HoTen": body.ho_ten.strip(), "SDT": body.sdt.strip()}


@router.post("/tickets", status_code=201)
def issue_tickets(
    body: IssueTicketRequest,
    user: dict = Depends(get_current_user),
):
    dp_meta = fetch_one(
        """
        SELECT dp.MaDP, dp.MaKH, dp.TrangThai, MIN(p.MaCN) AS MaCN, hd.MaHD
        FROM DAT_PHONG dp
        LEFT JOIN CT_DAT_PHONG c ON c.MaDP = dp.MaDP
        LEFT JOIN PHONG p ON p.MaPhong = c.MaPhong
        LEFT JOIN HOA_DON hd ON hd.MaDP = dp.MaDP
        WHERE dp.MaDP = %s
        GROUP BY dp.MaDP, dp.MaKH, dp.TrangThai, hd.MaHD
        """,
        (body.ma_dp,),
    )
    if not dp_meta:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt phòng")
    if dp_meta["TrangThai"] in ("Đã hủy", "Đã trả phòng"):
        raise HTTPException(status_code=400, detail=f"Không thể phát hành vé cho đơn ở trạng thái '{dp_meta['TrangThai']}'")

    loai_ve = fetch_one(
        """
        SELECT lv.MaLoaiVe, lv.TenLoaiVe, lv.GiaVe, kv.MaCN, kv.TenKhu
        FROM LOAI_VE lv
        JOIN KHU_VUI_CHOI kv ON kv.MaKhu = lv.MaKhu
        WHERE lv.MaLoaiVe = %s
        """,
        (body.ma_loai_ve,),
    )
    if not loai_ve:
        raise HTTPException(status_code=404, detail="Không tìm thấy loại vé")

    is_staff = user["is_admin"] or "SERVICE.RECORD_USE" in user["permissions"]
    if is_staff:
        ensure_branch_access(user, loai_ve["MaCN"])
    else:
        if user.get("MaKH") is None or int(user["MaKH"]) != int(dp_meta["MaKH"]):
            raise HTTPException(status_code=403, detail="Bạn không có quyền đặt vé cho đơn đặt phòng này")

    if dp_meta["MaCN"] is not None and int(dp_meta["MaCN"]) != int(loai_ve["MaCN"]):
        raise HTTPException(status_code=400, detail="Loại vé không thuộc cùng chi nhánh với đơn đặt phòng")

    validated_vouchers = []
    if body.voucher_code and body.voucher_code.strip():
        holiday_info = detect_holiday_range(body.ngay_su_dung, None)
        validated_vouchers = validate_voucher_selection(
            [body.voucher_code],
            is_holiday=holiday_info["is_holiday"],
            has_hotel=False,
            has_amusement=True,
        )

    issued = issue_tickets_tx(
        ma_dp=body.ma_dp,
        ma_kh=dp_meta["MaKH"],
        ma_hd=dp_meta["MaHD"],
        ma_loai_ve=body.ma_loai_ve,
        ngay_su_dung=body.ngay_su_dung,
        so_luong=body.so_luong,
        actor_ma_tk=user["MaTK"],
        expected_ma_cn=dp_meta["MaCN"],
    )

    applied_vouchers = []
    if validated_vouchers and dp_meta.get("MaHD"):
        applied_vouchers = apply_vouchers_tx(dp_meta["MaHD"], validated_vouchers, user["MaTK"])

    payment_qr = build_transfer_qr_info(dp_meta["MaHD"]) if dp_meta.get("MaHD") else None
    return {
        "message": f"Đã phát hành {len(issued)} vé điện tử mới",
        "tickets": issued,
        "MaHD": dp_meta.get("MaHD"),
        "applied_vouchers": applied_vouchers,
        "payment_qr": payment_qr,
    }


@router.post("/service-orders", status_code=201)
def create_service_order(
    body: ServiceOrderRequest,
    user: dict = Depends(get_current_user),
):
    dp_meta = fetch_one(
        """
        SELECT dp.MaDP, dp.MaKH, dp.TrangThai, hd.MaHD
        FROM DAT_PHONG dp
        LEFT JOIN HOA_DON hd ON hd.MaDP = dp.MaDP
        WHERE dp.MaDP = %s
        """,
        (body.ma_dp,),
    )
    if not dp_meta:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn đặt phòng")
    if dp_meta["TrangThai"] in ("Đã hủy", "Đã trả phòng"):
        raise HTTPException(status_code=400, detail=f"Đơn đặt phòng đang ở trạng thái '{dp_meta['TrangThai']}', không thể thêm dịch vụ")

    is_customer_owner = (
        user.get("MaKH") is not None
        and not user["is_admin"]
        and int(user["MaKH"]) == int(dp_meta["MaKH"])
    )

    if is_customer_owner:
        recorded = record_service_order_tx(
            ma_dp=body.ma_dp,
            ma_cn=body.ma_cn,
            ma_dv=body.ma_dv,
            so_luong=body.so_luong,
            actor_ma_tk=user["MaTK"],
        )
        payment_qr = build_transfer_qr_info(recorded["MaHD"]) if recorded.get("MaHD") else None
        return {
            "mode": "direct_customer",
            "message": f"Đã thêm dịch vụ {recorded['TenDV']} (x{recorded['SoLuong']}). Vui lòng quét QR để thanh toán.",
            "MaHD": recorded["MaHD"],
            "MaSD": recorded["MaSD"],
            "service": recorded,
            "payment_qr": payment_qr,
        }

    # Cac quyen han khac (Admin, Quan ly, Le tan, NV dich vu): gui thong bao de xuat ve tai khoan khach xac nhan
    is_staff = (
        user["is_admin"]
        or "SERVICE.RECORD_USE" in user["permissions"]
        or "BOOKING.READ_BRANCH" in user["permissions"]
        or "BOOKING.CONFIRM" in user["permissions"]
    )
    if not is_staff:
        raise HTTPException(status_code=403, detail="Bạn không có quyền đặt dịch vụ cho đơn này")

    ensure_branch_access(user, body.ma_cn)
    branch_match = fetch_one(
        """
        SELECT COUNT(*) AS cnt
        FROM CT_DAT_PHONG c
        JOIN PHONG p ON p.MaPhong = c.MaPhong
        WHERE c.MaDP = %s AND p.MaCN = %s
        """,
        (body.ma_dp, body.ma_cn),
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
        (body.ma_cn, body.ma_dv),
    )
    if not svc:
        raise HTTPException(status_code=404, detail="Chi nhánh không cung cấp dịch vụ này")
    if svc["TrangThai"] != "Đang cung cấp":
        raise HTTPException(status_code=400, detail=f"Dịch vụ '{svc['TenDV']}' hiện đang tạm ngưng tại chi nhánh")

    total_amount = float(svc["DonGia"]) * body.so_luong
    title = f"Đề xuất dịch vụ: {svc['TenDV']} (x{body.so_luong})"
    note_part = f" Ghi chú: {body.ghi_chu.strip()}." if body.ghi_chu and body.ghi_chu.strip() else ""
    content = (
        f"Nhân viên ({user['TenDangNhap']}) đã đặt đề xuất dịch vụ {svc['TenDV']} x{body.so_luong} "
        f"(tổng {int(total_amount):,}đ) cho đơn #{body.ma_dp}.{note_part} "
        f"Vui lòng bấm Xác nhận để ghi nhận vào hóa đơn hoặc Từ chối."
    )

    with get_cursor(autocommit=False) as cur:
        cur.execute(
            """
            INSERT INTO THONG_BAO_KHACH_HANG
                (MaKH, MaDP, LoaiTB, TieuDe, NoiDung, OtpCode, DuLieuJson, TrangThai, NguoiGuiMaTK, HetHanLuc)
            VALUES
                (%s, %s, 'SERVICE_CONFIRM', %s, %s, NULL,
                 JSON_OBJECT('ma_dp', %s, 'ma_cn', %s, 'ma_dv', %s, 'ten_dv', %s, 'so_luong', %s, 'don_gia', %s, 'thanh_tien', %s, 'ghi_chu', %s),
                 'Chờ xác nhận', %s, DATE_ADD(NOW(), INTERVAL 24 HOUR))
            """,
            (
                dp_meta["MaKH"],
                body.ma_dp,
                title,
                content,
                body.ma_dp,
                body.ma_cn,
                body.ma_dv,
                svc["TenDV"],
                body.so_luong,
                float(svc["DonGia"]),
                total_amount,
                (body.ghi_chu or "").strip(),
                user["MaTK"],
            ),
        )
        ma_tb = cur.lastrowid

    return {
        "mode": "pending_customer_confirm",
        "message": f"Đã gửi thông báo xác nhận dịch vụ '{svc['TenDV']}' đến tài khoản khách hàng",
        "MaTB": ma_tb,
        "MaDP": body.ma_dp,
    }


@router.patch("/services/{ma_cn}/{ma_dv}")
def update_branch_service(
    ma_cn: int,
    ma_dv: int,
    body: UpdateBranchServiceRequest,
    user: dict = Depends(require_permission("SERVICE.MANAGE_BRANCH")),
):
    ensure_branch_access(user, ma_cn)
    existing = fetch_one(
        "SELECT MaCN, MaDV, DonGia, TrangThai FROM DV_CHI_NHANH WHERE MaCN = %s AND MaDV = %s",
        (ma_cn, ma_dv),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Không tìm thấy dịch vụ tại chi nhánh")

    with get_cursor(autocommit=False) as cur:
        cur.execute(
            "UPDATE DV_CHI_NHANH SET DonGia = %s, TrangThai = %s WHERE MaCN = %s AND MaDV = %s",
            (body.don_gia, body.trang_thai, ma_cn, ma_dv),
        )
        cur.execute(
            """
            INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriCu, GiaTriMoi, LyDo)
            VALUES (%s, 'CAP_NHAT_DICH_VU_CN', 'DV_CHI_NHANH', %s,
                    JSON_OBJECT('DonGia', %s, 'TrangThai', %s),
                    JSON_OBJECT('DonGia', %s, 'TrangThai', %s),
                    'Quản lý cập nhật giá/trạng thái dịch vụ chi nhánh')
            """,
            (
                user["MaTK"],
                f"{ma_cn}:{ma_dv}",
                float(existing["DonGia"]),
                existing["TrangThai"],
                float(body.don_gia),
                body.trang_thai,
            ),
        )
    return {"message": "Đã cập nhật dịch vụ chi nhánh", "MaCN": ma_cn, "MaDV": ma_dv}
