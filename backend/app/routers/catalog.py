from fastapi import APIRouter, Query
from ..db import fetch_all

router = APIRouter(prefix="/api/catalog", tags=["Danh mục khách sạn"])


@router.get("/branches")
def list_branches():
    return fetch_all(
        """
        SELECT cn.MaCN, cn.TenCN, cn.DiaChi, cn.SDT, cn.Email,
               COUNT(p.MaPhong) AS TongSoPhong
        FROM CHI_NHANH cn
        LEFT JOIN PHONG p ON p.MaCN = cn.MaCN
        GROUP BY cn.MaCN, cn.TenCN, cn.DiaChi, cn.SDT, cn.Email
        ORDER BY cn.MaCN
        """
    )


@router.get("/room-types")
def list_room_types():
    return fetch_all(
        "SELECT MaLP, TenLP, MoTa, SucChua FROM LOAI_PHONG ORDER BY SucChua, MaLP"
    )


@router.get("/prices")
def list_prices(ma_lp: str | None = Query(default=None)):
    if ma_lp:
        return fetch_all(
            "SELECT * FROM BANG_GIA WHERE MaLP = %s ORDER BY MaBG", (ma_lp,)
        )
    return fetch_all("SELECT * FROM BANG_GIA ORDER BY MaLP, MaBG")


@router.get("/services")
def list_services(ma_cn: int | None = Query(default=None)):
    if ma_cn is not None:
        return fetch_all(
            """
            SELECT dcn.MaCN, cn.TenCN, dv.MaDV, dv.TenDV, dv.LoaiDV, dv.MoTa,
                   dcn.DonGia, dcn.TrangThai
            FROM DV_CHI_NHANH dcn
            JOIN DICH_VU dv ON dv.MaDV = dcn.MaDV
            JOIN CHI_NHANH cn ON cn.MaCN = dcn.MaCN
            WHERE dcn.MaCN = %s
            ORDER BY dv.LoaiDV, dv.TenDV
            """,
            (ma_cn,),
        )
    return fetch_all(
        "SELECT MaDV, TenDV, LoaiDV, MoTa FROM DICH_VU ORDER BY LoaiDV, MaDV"
    )


@router.get("/combos")
def list_combos(ma_cn: int | None = Query(default=None)):
    sql = """
        SELECT gc.*, cn.TenCN, lp.TenLP
        FROM GOI_COMBO gc
        JOIN CHI_NHANH cn ON cn.MaCN = gc.MaCN
        JOIN LOAI_PHONG lp ON lp.MaLP = gc.MaLP
    """
    if ma_cn is not None:
        return fetch_all(sql + " WHERE gc.MaCN = %s ORDER BY gc.MaCombo", (ma_cn,))
    return fetch_all(sql + " ORDER BY gc.MaCombo")


@router.get("/vouchers")
def list_active_vouchers():
    return fetch_all(
        """
        SELECT MaVoucher, Code, LoaiApDung, LoaiGiam, GiaTriGiam, DonHangToiThieu, GiamToiDa,
               SoLuongPhatHanh, SoLuongDaDung, NgayBatDau, NgayKetThuc, TrangThai
        FROM MA_GIAM_GIA
        ORDER BY TrangThai, NgayKetThuc DESC, MaVoucher
        """
    )


@router.get("/amusement-zones")
def list_amusement_zones(ma_cn: int | None = Query(default=None)):
    sql = """
        SELECT kv.*, cn.TenCN
        FROM KHU_VUI_CHOI kv
        JOIN CHI_NHANH cn ON cn.MaCN = kv.MaCN
    """
    if ma_cn is not None:
        return fetch_all(sql + " WHERE kv.MaCN = %s ORDER BY kv.MaKhu", (ma_cn,))
    return fetch_all(sql + " ORDER BY kv.MaKhu")


@router.get("/ticket-types")
def list_ticket_types(ma_cn: int | None = Query(default=None)):
    sql = """
        SELECT lv.MaLoaiVe, lv.MaKhu, lv.TenLoaiVe, lv.DoiTuong, lv.GiaVe, lv.KhungGio, lv.MoTa,
               kv.TenKhu, kv.MaCN, cn.TenCN
        FROM LOAI_VE lv
        JOIN KHU_VUI_CHOI kv ON kv.MaKhu = lv.MaKhu
        JOIN CHI_NHANH cn ON cn.MaCN = kv.MaCN
    """
    if ma_cn is not None:
        return fetch_all(
            sql + " WHERE kv.MaCN = %s ORDER BY kv.MaKhu, lv.MaLoaiVe", (ma_cn,)
        )
    return fetch_all(sql + " ORDER BY kv.MaCN, lv.MaLoaiVe")
