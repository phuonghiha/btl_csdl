import base64
import hmac
import re
from decimal import Decimal
from typing import Any

import pymysql
from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import fetch_all, fetch_one, get_cursor
from .finance import _crc16_ccitt

router = APIRouter(prefix="/api/bank", tags=["Ngân hàng & VietQR Webhook"])

BANK_BIN_NAMES = {
    "970422": ("MB", "MB Bank (Ngân hàng Quân đội)"),
    "970436": ("VCB", "Vietcombank"),
    "970415": ("ICB", "VietinBank"),
    "970418": ("BIDV", "BIDV"),
    "970407": ("TCB", "Techcombank"),
    "970432": ("VPB", "VPBank"),
    "970423": ("TPB", "TPBank"),
    "970405": ("VBA", "Agribank"),
    "970416": ("ACB", "ACB"),
}

HD_REGEX = re.compile(r"\bHD\s*#?\s*(\d+)\b", re.IGNORECASE)
DP_REGEX = re.compile(r"\bDP\s*#?\s*(\d+)\b", re.IGNORECASE)


class DecodeQrRequest(BaseModel):
    payload: str = Field(..., min_length=12, max_length=1024)


class DecodeQrImageRequest(BaseModel):
    image_base64: str = Field(..., min_length=20)


class BankWebhookRequest(BaseModel):
    # Mock Bank fields
    bank_code: str | None = Field(default=None, max_length=40)
    account_no: str | None = Field(default=None, max_length=60)
    transaction_id: str | None = Field(default=None, max_length=120)
    amount: Decimal | None = Field(default=None)
    memo: str | None = Field(default=None, max_length=300)
    transfer_type: str | None = Field(default="in", max_length=20)
    sender_account: str | None = Field(default=None, max_length=60)
    sender_name: str | None = Field(default=None, max_length=120)
    # SePay-compatible aliases
    gateway: str | None = Field(default=None, max_length=40)
    accountNumber: str | None = Field(default=None, max_length=60)
    referenceCode: str | None = Field(default=None, max_length=120)
    id: int | str | None = None
    transferAmount: Decimal | None = Field(default=None)
    content: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=300)
    transferType: str | None = Field(default=None, max_length=20)


def _parse_tlv_map(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    idx = 0
    n = len(raw)
    while idx + 4 <= n:
        tag = raw[idx : idx + 2]
        len_str = raw[idx + 2 : idx + 4]
        if not len_str.isdigit():
            raise ValueError(f"Độ dài TLV không hợp lệ tại vị trí {idx}")
        length = int(len_str)
        val_start = idx + 4
        val_end = val_start + length
        if val_end > n:
            raise ValueError(f"Chuỗi TLV bị cắt ngắn ở tag {tag}")
        result[tag] = raw[val_start:val_end]
        idx = val_end
    if idx != n:
        raise ValueError("Dữ liệu thừa ở cuối chuỗi TLV")
    return result


def parse_vietqr_payload(payload: str) -> dict[str, Any]:
    raw = payload.strip()
    if len(raw) < 20 or not raw.startswith("000201"):
        raise HTTPException(status_code=400, detail="Chuỗi không đúng định dạng VietQR EMVCo")

    try:
        top = _parse_tlv_map(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Không thể giải mã QR: {exc}") from exc

    crc_valid = False
    if len(raw) >= 8 and raw[-8:-4] == "6304":
        crc_valid = _crc16_ccitt(raw[:-4]).upper() == raw[-4:].upper()

    merchant_raw = top.get("38", "")
    bank_bin = ""
    account_no = ""
    service_code = ""
    if merchant_raw:
        try:
            m_tags = _parse_tlv_map(merchant_raw)
            service_code = m_tags.get("02", "")
            acc_raw = m_tags.get("01", "")
            if acc_raw:
                acc_tags = _parse_tlv_map(acc_raw)
                bank_bin = acc_tags.get("00", "")
                account_no = acc_tags.get("01", "")
        except ValueError:
            pass

    if not bank_bin or not account_no:
        raise HTTPException(status_code=400, detail="Không tìm thấy mã ngân hàng / số tài khoản trong mã QR")

    memo = ""
    extra_raw = top.get("62", "")
    if extra_raw:
        try:
            extra_tags = _parse_tlv_map(extra_raw)
            memo = extra_tags.get("08", "")
        except ValueError:
            pass

    amount_val: int | None = None
    if top.get("54"):
        try:
            amount_val = int(round(float(top["54"])))
        except ValueError:
            amount_val = None

    bank_code, bank_name = BANK_BIN_NAMES.get(bank_bin, (bank_bin, f"Ngân hàng (BIN {bank_bin})"))
    settings = get_settings()
    is_target_merchant = account_no == settings.bank_account_no and bank_bin == settings.bank_bin

    hd_match = HD_REGEX.search(memo)
    dp_match = DP_REGEX.search(memo)
    ma_hd = int(hd_match.group(1)) if hd_match else None
    ma_dp = int(dp_match.group(1)) if dp_match else None

    invoice_summary = None
    if ma_hd is not None:
        inv = fetch_one(
            """
            SELECT hd.MaHD, hd.MaDP, hd.TongTien, hd.TienCoc, hd.TrangThai,
                   COALESCE((
                       SELECT SUM(gd.SoTien)
                       FROM GIAO_DICH_THANH_TOAN gd
                       WHERE gd.MaHD = hd.MaHD AND gd.TrangThai = 'Thành công'
                   ), 0) AS TongDaThu
            FROM HOA_DON hd
            WHERE hd.MaHD = %s
            """,
            (ma_hd,),
        )
        if inv:
            tong_tien = float(inv["TongTien"] or 0)
            da_thu = float(inv["TongDaThu"] or 0)
            invoice_summary = {
                "ma_hd": inv["MaHD"],
                "ma_dp": inv["MaDP"],
                "trang_thai_hd": inv["TrangThai"],
                "tong_tien": tong_tien,
                "tien_coc": float(inv["TienCoc"] or 0),
                "da_thu": da_thu,
                "con_phai_tra": max(0.0, tong_tien - da_thu),
            }

    return {
        "crc_valid": crc_valid,
        "is_dynamic": top.get("01") == "12",
        "bank_bin": bank_bin,
        "bank_code": bank_code,
        "bank_name": bank_name,
        "account_no": account_no,
        "account_name": settings.bank_account_name if is_target_merchant else None,
        "is_target_merchant": is_target_merchant,
        "service_code": service_code,
        "currency": top.get("53", "704"),
        "country": top.get("58", "VN"),
        "amount": amount_val,
        "memo": memo,
        "ma_hd": ma_hd,
        "ma_dp": ma_dp,
        "invoice": invoice_summary,
    }


def _verify_bank_secret(x_bank_api_key: str | None, authorization: str | None) -> None:
    settings = get_settings()
    candidate = (x_bank_api_key or "").strip()
    if not candidate and authorization:
        parts = authorization.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() in ("apikey", "bearer"):
            candidate = parts[1].strip()
    if not candidate or not hmac.compare_digest(candidate, settings.bank_webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Bank-Api-Key không hợp lệ",
        )


@router.post("/decode-qr")
def decode_qr_payload(body: DecodeQrRequest):
    return parse_vietqr_payload(body.payload)


@router.post("/decode-qr-image")
def decode_qr_image(body: DecodeQrImageRequest):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="Server chưa cài OpenCV để giải mã ảnh; vui lòng dùng camera hoặc dán chuỗi QR.",
        ) from exc

    raw_b64 = body.image_base64.strip()
    if "," in raw_b64 and raw_b64.startswith("data:"):
        raw_b64 = raw_b64.split(",", 1)[1]
    if len(raw_b64) > 10_000_000:
        raise HTTPException(status_code=400, detail="Ảnh quá lớn (tối đa ~7MB)")

    try:
        img_bytes = base64.b64decode(raw_b64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Dữ liệu ảnh base64 không hợp lệ") from exc

    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Không đọc được định dạng ảnh")

    detector = cv2.QRCodeDetector()
    text, _, _ = detector.detectAndDecode(img)
    if not text:
        raise HTTPException(status_code=400, detail="Không tìm thấy mã QR hợp lệ trong ảnh")

    parsed = parse_vietqr_payload(text)
    parsed["raw_payload"] = text
    return parsed


@router.post("/webhook")
def receive_bank_webhook(
    body: BankWebhookRequest,
    x_bank_api_key: str | None = Header(default=None, alias="X-Bank-Api-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    _verify_bank_secret(x_bank_api_key, authorization)

    transfer_dir = (body.transfer_type or body.transferType or "in").strip().lower()
    if transfer_dir == "out":
        return {"status": "ignored", "reason": "Bỏ qua giao dịch tiền ra"}

    settings = get_settings()
    account_no = (body.account_no or body.accountNumber or "").strip()
    if account_no != settings.bank_account_no:
        raise HTTPException(
            status_code=400,
            detail=f"Số tài khoản thụ hưởng '{account_no}' không khớp tài khoản gốc '{settings.bank_account_no}'",
        )

    amount = body.amount if body.amount is not None else body.transferAmount
    if amount is None or amount <= 0:
        raise HTTPException(status_code=400, detail="Số tiền giao dịch phải lớn hơn 0")

    tx_id_raw = body.transaction_id or body.referenceCode or (str(body.id) if body.id is not None else "")
    tx_id = tx_id_raw.strip()
    if not tx_id:
        raise HTTPException(status_code=400, detail="Thiếu mã giao dịch ngân hàng (transaction_id)")

    memo = (body.memo or body.content or body.description or "").strip()
    hd_match = HD_REGEX.search(memo)
    if not hd_match:
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy mã hóa đơn (dạng HD<số>) trong nội dung chuyển khoản",
        )
    ma_hd = int(hd_match.group(1))

    invoice = fetch_one("SELECT MaHD, MaDP, TongTien, TienCoc, TrangThai FROM HOA_DON WHERE MaHD = %s", (ma_hd,))
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy hóa đơn #{ma_hd}")

    gateway_name = "VIETQR_BANK"
    existing = fetch_one(
        """
        SELECT MaGiaoDich, MaHD, SoTien, ThoiGianGD, NoiDungChuyenKhoan
        FROM GIAO_DICH_THANH_TOAN
        WHERE CongThanhToan = %s AND MaGiaoDichCong = %s
        """,
        (gateway_name, tx_id),
    )
    if existing:
        return {
            "status": "already_processed",
            "duplicate": True,
            "message": f"Giao dịch {tx_id} đã được ghi nhận trước đó (chống cộng trùng)",
            "ma_giao_dich": existing["MaGiaoDich"],
            "ma_hd": existing["MaHD"],
            "so_tien": float(existing["SoTien"]),
        }

    sender_suffix = ""
    if body.sender_name or body.sender_account:
        sender_parts = [p for p in [body.sender_name, body.sender_account] if p]
        sender_suffix = f" [Từ: {' - '.join(sender_parts)}]"
    memo_stored = f"{memo}{sender_suffix}"[:300]

    try:
        with get_cursor() as cur:
            cur.execute(
                "CALL sp_ghi_nhan_thanh_toan(%s, %s, %s, %s, %s, NULL)",
                (ma_hd, gateway_name, tx_id, str(amount), memo_stored),
            )
    except pymysql.err.IntegrityError as exc:
        if exc.args and exc.args[0] == 1062:
            return {
                "status": "already_processed",
                "duplicate": True,
                "message": f"Giao dịch {tx_id} đã được ghi nhận trước đó",
                "ma_hd": ma_hd,
            }
        raise

    updated = fetch_one(
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
    tong_tien = float(updated["TongTien"] or 0)
    tien_coc = float(updated["TienCoc"] or 0)
    da_thu = float(updated["TongDaThu"] or 0)
    con_lai = max(0.0, tong_tien - da_thu)

    auto_confirmed = False
    auto_confirm_note = None
    required_deposit = min(tien_coc, tong_tien) if tien_coc > 0 else tong_tien
    if updated["TrangThaiDP"] == "Chờ xác nhận" and da_thu > 0 and da_thu >= required_deposit:
        try:
            with get_cursor() as cur:
                cur.execute("CALL sp_xac_nhan_dat_phong(%s, NULL)", (updated["MaDP"],))
            auto_confirmed = True
        except pymysql.err.OperationalError as exc:
            auto_confirm_note = exc.args[1] if len(exc.args) > 1 else str(exc)

    return {
        "status": "processed",
        "duplicate": False,
        "message": f"Đã nhận {int(round(float(amount))):,} VND cho HĐ #{ma_hd}",
        "ma_hd": ma_hd,
        "ma_dp": updated["MaDP"],
        "transaction_id": tx_id,
        "bank_code": (body.bank_code or body.gateway or settings.bank_code).upper(),
        "account_no": account_no,
        "amount": float(amount),
        "memo": memo,
        "tong_tien": tong_tien,
        "da_thu": da_thu,
        "con_phai_tra": con_lai,
        "trang_thai_hd": updated["TrangThaiHD"],
        "auto_confirmed": auto_confirmed,
        "auto_confirm_note": auto_confirm_note,
    }


@router.get("/recent-transfers")
def list_recent_bank_transfers(
    x_bank_api_key: str | None = Header(default=None, alias="X-Bank-Api-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
):
    _verify_bank_secret(x_bank_api_key, authorization)
    settings = get_settings()
    rows = fetch_all(
        """
        SELECT gd.MaGiaoDich, gd.MaHD, hd.MaDP, gd.CongThanhToan, gd.MaGiaoDichCong,
               gd.SoTien, gd.ThoiGianGD, gd.TrangThai, gd.NoiDungChuyenKhoan
        FROM GIAO_DICH_THANH_TOAN gd
        JOIN HOA_DON hd ON hd.MaHD = gd.MaHD
        WHERE gd.CongThanhToan IN ('VIETQR_BANK', 'CHUYEN_KHOAN')
        ORDER BY gd.ThoiGianGD DESC, gd.MaGiaoDich DESC
        LIMIT 25
        """
    )
    return {
        "account_no": settings.bank_account_no,
        "account_name": settings.bank_account_name,
        "bank_code": settings.bank_code,
        "transfers": rows,
    }
