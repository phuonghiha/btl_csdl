import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import fetch_all, fetch_one, get_cursor
from ..security import get_current_user
from ..services.booking_rules import record_service_order_tx
from .finance import build_transfer_qr_info

router = APIRouter(prefix="/api/notifications", tags=["Thông báo & Xác nhận khách hàng"])


class RespondNotificationRequest(BaseModel):
    action: str = Field(..., pattern="^(confirm|reject)$")
    ly_do: str | None = Field(default=None, max_length=300)


def _expire_stale_notifications() -> None:
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE THONG_BAO_KHACH_HANG
            SET TrangThai = 'Hết hạn'
            WHERE TrangThai = 'Chờ xác nhận'
              AND HetHanLuc IS NOT NULL
              AND HetHanLuc < NOW()
            """
        )


def _deserialize_row(row: dict[str, Any], include_otp: bool) -> dict[str, Any]:
    raw_json = row.get("DuLieuJson")
    if isinstance(raw_json, (str, bytes)):
        try:
            row["DuLieuJson"] = json.loads(raw_json)
        except Exception:
            pass
    if not include_otp:
        row["OtpCode"] = None
    return row


@router.get("")
def list_notifications(
    ma_dp: int | None = Query(default=None),
    user: dict = Depends(get_current_user),
):
    _expire_stale_notifications()

    if user.get("MaKH"):
        clauses = ["tb.MaKH = %s"]
        params: list[Any] = [user["MaKH"]]
        if ma_dp is not None:
            clauses.append("tb.MaDP = %s")
            params.append(ma_dp)
        rows = fetch_all(
            f"""
            SELECT tb.MaTB, tb.MaKH, tb.MaDP, tb.LoaiTB, tb.TieuDe, tb.NoiDung,
                   tb.OtpCode, tb.DuLieuJson, tb.TrangThai, tb.NguoiGuiMaTK,
                   tb.ThoiGianTao, tb.HetHanLuc, tb.ThoiGianPhanHoi,
                   tk.TenDangNhap AS NguoiGuiTen
            FROM THONG_BAO_KHACH_HANG tb
            LEFT JOIN TAI_KHOAN tk ON tk.MaTK = tb.NguoiGuiMaTK
            WHERE {' AND '.join(clauses)}
            ORDER BY FIELD(tb.TrangThai, 'Chờ xác nhận', 'Đã xác nhận', 'Đã từ chối', 'Hết hạn'),
                     tb.ThoiGianTao DESC
            LIMIT 50
            """,
            tuple(params),
        )
        items = [_deserialize_row(r, include_otp=True) for r in rows]
        unread_count = sum(1 for item in items if item["TrangThai"] == "Chờ xác nhận")
        return {"unread_count": unread_count, "items": items}

    # Nhan vien / Admin xem trang thai xac nhan (AN ma OtpCode)
    is_staff = user["is_admin"] or "BOOKING.READ_BRANCH" in user["permissions"] or "SERVICE.RECORD_USE" in user["permissions"]
    if not is_staff:
        return {"unread_count": 0, "items": []}

    clauses = ["1=1"]
    params = []
    if ma_dp is not None:
        clauses.append("tb.MaDP = %s")
        params.append(ma_dp)
    if not user["is_admin"] and user.get("MaCN") is not None:
        clauses.append(
            """
            EXISTS (
                SELECT 1 FROM CT_DAT_PHONG c
                JOIN PHONG p ON p.MaPhong = c.MaPhong
                WHERE c.MaDP = tb.MaDP AND p.MaCN = %s
            )
            """
        )
        params.append(user["MaCN"])

    rows = fetch_all(
        f"""
        SELECT tb.MaTB, tb.MaKH, tb.MaDP, tb.LoaiTB, tb.TieuDe, tb.NoiDung,
               NULL AS OtpCode, tb.DuLieuJson, tb.TrangThai, tb.NguoiGuiMaTK,
               tb.ThoiGianTao, tb.HetHanLuc, tb.ThoiGianPhanHoi,
               tk.TenDangNhap AS NguoiGuiTen
        FROM THONG_BAO_KHACH_HANG tb
        LEFT JOIN TAI_KHOAN tk ON tk.MaTK = tb.NguoiGuiMaTK
        WHERE {' AND '.join(clauses)}
        ORDER BY tb.ThoiGianTao DESC
        LIMIT 50
        """,
        tuple(params),
    )
    items = [_deserialize_row(r, include_otp=False) for r in rows]
    unread_count = sum(1 for item in items if item["TrangThai"] == "Chờ xác nhận")
    return {"unread_count": unread_count, "items": items}


@router.post("/{ma_tb}/respond")
def respond_notification(
    ma_tb: int,
    body: RespondNotificationRequest,
    user: dict = Depends(get_current_user),
):
    _expire_stale_notifications()

    tb = fetch_one(
        """
        SELECT MaTB, MaKH, MaDP, LoaiTB, TieuDe, DuLieuJson, TrangThai, HetHanLuc
        FROM THONG_BAO_KHACH_HANG
        WHERE MaTB = %s
        """,
        (ma_tb,),
    )
    if not tb:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")
    if not user.get("MaKH") or int(user["MaKH"]) != int(tb["MaKH"]):
        raise HTTPException(status_code=403, detail="Chỉ tài khoản khách hàng sở hữu mới có quyền xác nhận thông báo này")
    if tb["TrangThai"] != "Chờ xác nhận":
        raise HTTPException(status_code=400, detail=f"Thông báo đã ở trạng thái '{tb['TrangThai']}'")
    if tb["HetHanLuc"] and tb["HetHanLuc"] < datetime.now():
        with get_cursor() as cur:
            cur.execute("UPDATE THONG_BAO_KHACH_HANG SET TrangThai = 'Hết hạn' WHERE MaTB = %s", (ma_tb,))
        raise HTTPException(status_code=400, detail="Thông báo đã hết hạn")

    if body.action == "reject":
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE THONG_BAO_KHACH_HANG
                SET TrangThai = 'Đã từ chối', ThoiGianPhanHoi = NOW()
                WHERE MaTB = %s
                """,
                (ma_tb,),
            )
        return {"message": "Đã từ chối yêu cầu", "MaTB": ma_tb, "TrangThai": "Đã từ chối"}

    # action == "confirm"
    payload = tb.get("DuLieuJson")
    if isinstance(payload, (str, bytes)):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}

    if tb["LoaiTB"] == "SERVICE_CONFIRM":
        ma_cn = payload.get("ma_cn")
        ma_dv = payload.get("ma_dv")
        so_luong = payload.get("so_luong", 1)
        if not ma_cn or not ma_dv:
            raise HTTPException(status_code=400, detail="Dữ liệu dịch vụ trong thông báo không hợp lệ")
        recorded = record_service_order_tx(
            ma_dp=int(tb["MaDP"]),
            ma_cn=int(ma_cn),
            ma_dv=int(ma_dv),
            so_luong=int(so_luong),
            actor_ma_tk=int(user["MaTK"]),
        )
        with get_cursor() as cur:
            cur.execute(
                """
                UPDATE THONG_BAO_KHACH_HANG
                SET TrangThai = 'Đã xác nhận', ThoiGianPhanHoi = NOW()
                WHERE MaTB = %s
                """,
                (ma_tb,),
            )
        payment_qr = build_transfer_qr_info(recorded["MaHD"]) if recorded.get("MaHD") else None
        return {
            "message": f"Đã xác nhận dịch vụ {recorded['TenDV']} (x{recorded['SoLuong']})",
            "MaTB": ma_tb,
            "TrangThai": "Đã xác nhận",
            "MaHD": recorded["MaHD"],
            "MaSD": recorded["MaSD"],
            "payment_qr": payment_qr,
        }

    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE THONG_BAO_KHACH_HANG
            SET TrangThai = 'Đã xác nhận', ThoiGianPhanHoi = NOW()
            WHERE MaTB = %s
            """,
            (ma_tb,),
        )
    return {"message": "Đã xác nhận thông báo", "MaTB": ma_tb, "TrangThai": "Đã xác nhận"}
