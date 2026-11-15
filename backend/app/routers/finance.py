from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import call_proc_with_out, fetch_all, fetch_one, get_cursor
from ..security import ensure_branch_access, get_current_user, require_permission

router = APIRouter(prefix="/api/invoices", tags=["Hóa đơn & Thanh toán"])


class PaymentRequest(BaseModel):
    cong_thanh_toan: str = Field(..., min_length=2, max_length=40)
    ma_giao_dich_cong: str | None = Field(default=None, max_length=120)
    so_tien: Decimal = Field(..., gt=0)
    noi_dung: str | None = Field(default=None, max_length=300)


class ApplyVoucherRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=60)


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def _crc16_ccitt(payload: str) -> str:
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def build_transfer_qr_info(
    ma_hd: int,
    mode: str = "full",
    custom_amount: Decimal | None = None,
) -> dict[str, Any]:
    meta = fetch_one(
        """
        SELECT hd.MaHD, hd.MaDP, hd.TongTien, hd.TrangThai,
               MIN(cn.TenCN) AS TenCN,
               COALESCE((
                   SELECT SUM(gd.SoTien)
                   FROM GIAO_DICH_THANH_TOAN gd
                   WHERE gd.MaHD = hd.MaHD AND gd.TrangThai = 'Thành công'
               ), 0) AS TongDaThu
        FROM HOA_DON hd
        LEFT JOIN CT_DAT_PHONG c ON c.MaDP = hd.MaDP
        LEFT JOIN PHONG p ON p.MaPhong = c.MaPhong
        LEFT JOIN CHI_NHANH cn ON cn.MaCN = p.MaCN
        WHERE hd.MaHD = %s
        GROUP BY hd.MaHD, hd.MaDP, hd.TongTien, hd.TrangThai
        """,
        (ma_hd,),
    )
    if not meta:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")

    tong_tien = float(meta["TongTien"] or 0)
    da_thu = float(meta["TongDaThu"] or 0)
    con_lai = max(0.0, tong_tien - da_thu)

    if custom_amount is not None:
        so_tien = max(0, int(round(float(custom_amount))))
    elif mode == "deposit":
        so_tien = max(0, int(round(con_lai * 0.30)))
    else:
        so_tien = max(0, int(round(con_lai)))

    settings = get_settings()
    bank_code = settings.bank_code
    bank_bin = settings.bank_bin
    bank_name = settings.bank_name
    account_no = settings.bank_account_no
    account_name = settings.bank_account_name
    noi_dung = f"TT HD{ma_hd} DP{meta['MaDP']}"

    merchant_info = _tlv(
        "38",
        _tlv("00", "A000000727")
        + _tlv("01", _tlv("00", bank_bin) + _tlv("01", account_no))
        + _tlv("02", "QRIBFTTA"),
    )
    parts = [
        _tlv("00", "01"),
        _tlv("01", "12" if so_tien > 0 else "11"),
        merchant_info,
        _tlv("53", "704"),
    ]
    if so_tien > 0:
        parts.append(_tlv("54", str(so_tien)))
    parts.extend([
        _tlv("58", "VN"),
        _tlv("62", _tlv("08", noi_dung)),
    ])
    raw_without_crc = "".join(parts) + "6304"
    vietqr_payload = raw_without_crc + _crc16_ccitt(raw_without_crc)

    qs = urlencode({
        "amount": so_tien,
        "addInfo": noi_dung,
        "accountName": account_name,
    })
    vietqr_image_url = f"https://img.vietqr.io/image/{bank_code}-{account_no}-compact2.png?{qs}"

    return {
        "ma_hd": ma_hd,
        "ma_dp": meta["MaDP"],
        "ten_cn": meta["TenCN"] or "Chuỗi khách sạn Aurelia",
        "trang_thai_hd": meta["TrangThai"],
        "bank_code": bank_code,
        "bank_bin": bank_bin,
        "bank_name": bank_name,
        "account_no": account_no,
        "account_name": account_name,
        "tong_tien": tong_tien,
        "da_thu": da_thu,
        "con_phai_tra": con_lai,
        "so_tien_chuyen": so_tien,
        "noi_dung": noi_dung,
        "vietqr_payload": vietqr_payload,
        "vietqr_image_url": vietqr_image_url,
    }


def _get_invoice_meta(ma_hd: int) -> dict[str, Any]:
    row = fetch_one(
        """
        SELECT hd.MaHD, hd.MaDP, hd.TongTien, hd.TienCoc, hd.TrangThai,
               dp.MaKH, MIN(p.MaCN) AS MaCN
        FROM HOA_DON hd
        JOIN DAT_PHONG dp ON dp.MaDP = hd.MaDP
        LEFT JOIN CT_DAT_PHONG c ON c.MaDP = dp.MaDP
        LEFT JOIN PHONG p ON p.MaPhong = c.MaPhong
        WHERE hd.MaHD = %s
        GROUP BY hd.MaHD, hd.MaDP, hd.TongTien, hd.TienCoc, hd.TrangThai, dp.MaKH
        """,
        (ma_hd,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Không tìm thấy hóa đơn")
    return row


@router.get("")
def list_invoices(
    ma_cn: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    can_branch = user["is_admin"] or "INVOICE.READ_BRANCH" in user["permissions"]
    can_self = "INVOICE.READ_SELF" in user["permissions"]
    if not can_branch and not can_self:
        raise HTTPException(status_code=403, detail="Không có quyền xem hóa đơn")

    clauses = []
    params: list[Any] = []
    if can_branch:
        if ma_cn is not None:
            ensure_branch_access(user, ma_cn)
            clauses.append("dp_cn.MaCN = %s")
            params.append(ma_cn)
        elif not user["is_admin"]:
            if not user["branch_ids"]:
                return []
            ph = ", ".join(["%s"] * len(user["branch_ids"]))
            clauses.append(f"dp_cn.MaCN IN ({ph})")
            params.extend(user["branch_ids"])
    else:
        if user["MaKH"] is None:
            return []
        clauses.append("dp.MaKH = %s")
        params.append(user["MaKH"])

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    return fetch_all(
        f"""
        SELECT hd.MaHD, hd.MaDP, hd.NgayLap, hd.TongTien, hd.TienCoc, hd.TrangThai,
               kh.MaKH, kh.HoTen AS TenKhachHang, dp_cn.MaCN, cn.TenCN,
               COALESCE(gd_ok.TongDaThu, 0) AS TongDaThu,
               (hd.TongTien - COALESCE(gd_ok.TongDaThu, 0)) AS ConPhaiTra
        FROM HOA_DON hd
        JOIN DAT_PHONG dp ON dp.MaDP = hd.MaDP
        JOIN KHACH_HANG kh ON kh.MaKH = dp.MaKH
        LEFT JOIN (
            SELECT DISTINCT c.MaDP, p.MaCN
            FROM CT_DAT_PHONG c
            JOIN PHONG p ON p.MaPhong = c.MaPhong
        ) dp_cn ON dp_cn.MaDP = dp.MaDP
        LEFT JOIN CHI_NHANH cn ON cn.MaCN = dp_cn.MaCN
        LEFT JOIN (
            SELECT MaHD, SUM(SoTien) AS TongDaThu
            FROM GIAO_DICH_THANH_TOAN
            WHERE TrangThai = 'Thành công'
            GROUP BY MaHD
        ) gd_ok ON gd_ok.MaHD = hd.MaHD
        {where_sql}
        ORDER BY hd.MaHD DESC
        LIMIT %s
        """,
        params,
    )


@router.get("/{ma_hd}")
def get_invoice_detail(ma_hd: int, user: dict = Depends(get_current_user)):
    meta = _get_invoice_meta(ma_hd)
    can_branch = user["is_admin"] or "INVOICE.READ_BRANCH" in user["permissions"]
    if can_branch:
        if meta["MaCN"] is not None:
            ensure_branch_access(user, meta["MaCN"])
    elif "INVOICE.READ_SELF" in user["permissions"] and user["MaKH"] == meta["MaKH"]:
        pass
    else:
        raise HTTPException(status_code=403, detail="Không có quyền xem hóa đơn này")

    items = fetch_all("SELECT * FROM CT_HOA_DON WHERE MaHD = %s ORDER BY MaCTHD", (ma_hd,))
    payments = fetch_all(
        "SELECT * FROM GIAO_DICH_THANH_TOAN WHERE MaHD = %s ORDER BY ThoiGianGD DESC",
        (ma_hd,),
    )
    return {"invoice": meta, "items": items, "payments": payments}


@router.get("/{ma_hd}/payment-status")
def get_invoice_payment_status(
    ma_hd: int,
    user: dict = Depends(get_current_user),
):
    meta = _get_invoice_meta(ma_hd)
    can_branch = user["is_admin"] or "INVOICE.READ_BRANCH" in user["permissions"] or "BOOKING.CREATE" in user["permissions"]
    if can_branch and user["MaKH"] is None:
        if meta["MaCN"] is not None:
            ensure_branch_access(user, meta["MaCN"])
    elif ("INVOICE.READ_SELF" in user["permissions"] or "BOOKING.CREATE" in user["permissions"]) and user["MaKH"] == meta["MaKH"]:
        pass
    else:
        raise HTTPException(status_code=403, detail="Không có quyền xem trạng thái thanh toán hóa đơn này")

    row = fetch_one(
        """
        SELECT hd.MaHD, hd.MaDP, hd.TongTien, hd.TienCoc, hd.TrangThai AS TrangThaiHD,
               dp.TrangThai AS TrangThaiDP,
               COALESCE((
                   SELECT SUM(gd.SoTien)
                   FROM GIAO_DICH_THANH_TOAN gd
                   WHERE gd.MaHD = hd.MaHD AND gd.TrangThai = 'Thành công'
               ), 0) AS TongDaThu
        FROM HOA_DON hd
        JOIN DAT_PHONG dp ON dp.MaDP = hd.MaDP
        WHERE hd.MaHD = %s
        """,
        (ma_hd,),
    )
    latest_payment = fetch_one(
        """
        SELECT MaGiaoDich, CongThanhToan, MaGiaoDichCong, SoTien, ThoiGianGD, NoiDungChuyenKhoan
        FROM GIAO_DICH_THANH_TOAN
        WHERE MaHD = %s AND TrangThai = 'Thành công'
        ORDER BY ThoiGianGD DESC, MaGiaoDich DESC
        LIMIT 1
        """,
        (ma_hd,),
    )
    tong_tien = float(row["TongTien"] or 0)
    da_thu = float(row["TongDaThu"] or 0)
    return {
        "ma_hd": row["MaHD"],
        "ma_dp": row["MaDP"],
        "trang_thai_hd": row["TrangThaiHD"],
        "trang_thai_dp": row["TrangThaiDP"],
        "tong_tien": tong_tien,
        "tien_coc": float(row["TienCoc"] or 0),
        "da_thu": da_thu,
        "con_phai_tra": max(0.0, tong_tien - da_thu),
        "latest_payment": latest_payment,
    }


@router.get("/{ma_hd}/payment-qr")
def get_invoice_payment_qr(
    ma_hd: int,
    mode: str = Query(default="full", pattern="^(full|deposit)$"),
    amount: Decimal | None = Query(default=None, gt=0),
    user: dict = Depends(get_current_user),
):
    meta = _get_invoice_meta(ma_hd)
    can_branch = user["is_admin"] or "INVOICE.READ_BRANCH" in user["permissions"] or "BOOKING.CREATE" in user["permissions"]
    if can_branch and user["MaKH"] is None:
        if meta["MaCN"] is not None:
            ensure_branch_access(user, meta["MaCN"])
    elif ("INVOICE.READ_SELF" in user["permissions"] or "BOOKING.CREATE" in user["permissions"]) and user["MaKH"] == meta["MaKH"]:
        pass
    else:
        raise HTTPException(status_code=403, detail="Không có quyền lấy mã QR thanh toán cho hóa đơn này")

    return build_transfer_qr_info(ma_hd, mode=mode, custom_amount=amount)


@router.post("/{ma_hd}/payments", status_code=201)
def record_payment(
    ma_hd: int,
    body: PaymentRequest,
    user: dict = Depends(require_permission("INVOICE.MANAGE")),
):
    meta = _get_invoice_meta(ma_hd)
    if meta["MaCN"] is not None:
        ensure_branch_access(user, meta["MaCN"])

    with get_cursor() as cur:
        cur.execute(
            "CALL sp_ghi_nhan_thanh_toan(%s, %s, %s, %s, %s, %s)",
            (
                ma_hd,
                body.cong_thanh_toan.strip(),
                body.ma_giao_dich_cong,
                str(body.so_tien),
                body.noi_dung,
                user["MaTK"],
            ),
        )
    return {"message": "Đã ghi nhận thanh toán", "MaHD": ma_hd}


@router.post("/{ma_hd}/apply-voucher")
def apply_voucher(
    ma_hd: int,
    body: ApplyVoucherRequest,
    user: dict = Depends(require_permission("INVOICE.MANAGE")),
):
    meta = _get_invoice_meta(ma_hd)
    if meta["MaCN"] is not None:
        ensure_branch_access(user, meta["MaCN"])

    out = call_proc_with_out(
        "sp_ap_ma_giam_gia",
        (ma_hd, body.code.strip(), user["MaTK"]),
        ["SoTienGiam"],
    )
    return {"message": "Đã áp mã giảm giá", "MaHD": ma_hd, "SoTienGiam": out.get("SoTienGiam")}
