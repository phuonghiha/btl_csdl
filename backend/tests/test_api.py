from datetime import date

from fastapi.testclient import TestClient

from app.db import get_cursor
from app.main import app

client = TestClient(app)


def _login(username: str, password: str = "Demo@123456") -> str:
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_and_catalog():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    branches = client.get("/api/catalog/branches")
    assert branches.status_code == 200
    assert len(branches.json()) == 10

    room_types = client.get("/api/catalog/room-types")
    assert room_types.status_code == 200
    assert len(room_types.json()) == 6

    avail = client.get(
        "/api/bookings/availability",
        params={"ma_cn": 1, "ngay_checkin": "2025-01-29", "ngay_checkout": "2025-02-01", "suc_chua": 2},
    )
    assert avail.status_code == 200
    rooms = avail.json()
    assert len(rooms) > 0
    lp001 = next(x for x in rooms if x["MaLP"] == "LP001")
    assert float(lp001["DonGiaDemDau"]) == 1104000.0


def test_rbac_and_branch_scoping():
    admin_tok = _login("admin_hethong")
    letan_tok = _login("letan_cn1")
    khach_tok = _login("khach_an")

    # Le tan CN1 xem phong CN1 OK, xem phong CN2 bi 403
    r_ok = client.get("/api/operations/rooms", params={"ma_cn": 1}, headers=_headers(letan_tok))
    assert r_ok.status_code == 200
    r_deny = client.get("/api/operations/rooms", params={"ma_cn": 2}, headers=_headers(letan_tok))
    assert r_deny.status_code == 403

    # Khach hang chi xem duoc dat phong cua chinh minh, khong vao duoc admin
    r_self = client.get("/api/bookings", headers=_headers(khach_tok))
    assert r_self.status_code == 200
    assert all(row["MaKH"] == 1 for row in r_self.json())

    r_admin_deny = client.get("/api/admin/dashboard", headers=_headers(khach_tok))
    assert r_admin_deny.status_code == 403

    # Admin xem duoc dashboard va users
    r_dash = client.get("/api/admin/dashboard", headers=_headers(admin_tok))
    assert r_dash.status_code == 200
    assert len(r_dash.json()["revenue_by_branch"]) == 10

    r_users = client.get("/api/admin/users", headers=_headers(admin_tok))
    assert r_users.status_code == 200
    assert len(r_users.json()) >= 5

    r_shifts = client.get(
        "/api/admin/staff-shifts",
        params={"thang": "2025-07"},
        headers=_headers(admin_tok),
    )
    assert r_shifts.status_code == 200, r_shifts.text
    assert len(r_shifts.json()) > 0

    r_logs = client.get("/api/admin/audit-logs", headers=_headers(admin_tok))
    assert r_logs.status_code == 200, r_logs.text


def test_booking_lifecycle_and_overlap_guard():
    letan_tok = _login("letan_cn1")
    khach_tok = _login("khach_an")

    # Dat trung phong voi mot don dang hoat dong bi chan 400 tu procedure/trigger
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT c.MaPhong, c.NgayCheckIn, c.NgayCheckOut
            FROM CT_DAT_PHONG c
            JOIN DAT_PHONG d ON d.MaDP = c.MaDP
            WHERE d.TrangThai IN ('Đã xác nhận', 'Đang lưu trú')
            ORDER BY c.MaDP DESC
            LIMIT 1
            """
        )
        busy_slot = cur.fetchone()
    assert busy_slot is not None
    overlap = client.post(
        "/api/bookings",
        json={
            "ma_phong": busy_slot["MaPhong"],
            "ngay_checkin": str(busy_slot["NgayCheckIn"]),
            "ngay_checkout": str(busy_slot["NgayCheckOut"]),
            "ghi_chu": "Test overlap",
        },
        headers=_headers(khach_tok),
    )
    assert overlap.status_code == 400

    # Dat phong moi hop le -> xac nhan -> check-in -> ghi nhan dich vu -> thanh toan -> check-out
    created = client.post(
        "/api/bookings",
        json={
            "ma_phong": 3,
            "ngay_checkin": "2026-12-10",
            "ngay_checkout": "2026-12-12",
            "ghi_chu": "Pytest API flow",
        },
        headers=_headers(khach_tok),
    )
    assert created.status_code == 201, created.text
    ma_dp = created.json()["MaDP"]
    ma_hd = created.json()["MaHD"]
    qr_full = created.json().get("payment_qr")
    assert qr_full and qr_full["vietqr_payload"].startswith("000201")
    assert qr_full["so_tien_chuyen"] > 0

    try:
        qr_dep = client.get(
            f"/api/invoices/{ma_hd}/payment-qr",
            params={"mode": "deposit"},
            headers=_headers(khach_tok),
        )
        assert qr_dep.status_code == 200, qr_dep.text
        assert qr_dep.json()["so_tien_chuyen"] < qr_full["so_tien_chuyen"]
        assert client.post(f"/api/bookings/{ma_dp}/confirm", headers=_headers(letan_tok)).status_code == 200
        assert client.post(f"/api/bookings/{ma_dp}/check-in", headers=_headers(letan_tok)).status_code == 200

        svc = client.post(
            "/api/operations/service-usages",
            json={"ma_dp": ma_dp, "ma_cn": 1, "ma_dv": 1, "so_luong": 1},
            headers=_headers(letan_tok),
        )
        assert svc.status_code == 201, svc.text

        inv = client.get(f"/api/invoices/{ma_hd}", headers=_headers(letan_tok))
        assert inv.status_code == 200
        tong_tien = inv.json()["invoice"]["TongTien"]
        assert float(tong_tien) > 0

        pay = client.post(
            f"/api/invoices/{ma_hd}/payments",
            json={
                "cong_thanh_toan": "VNPAY",
                "ma_giao_dich_cong": f"TEST-API-{ma_hd}",
                "so_tien": str(tong_tien),
                "noi_dung": "Thanh toan test API",
            },
            headers=_headers(letan_tok),
        )
        assert pay.status_code == 201, pay.text

        assert client.post(f"/api/bookings/{ma_dp}/check-out", headers=_headers(letan_tok)).status_code == 200
    finally:
        with get_cursor() as cur:
            cur.execute("DELETE FROM NHAT_KY_HOAT_DONG WHERE MaNhatKy > 1")
            cur.execute("DELETE FROM VE_DIEN_TU WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM SU_DUNG_DV WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM GIAO_DICH_THANH_TOAN WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM CT_HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM CT_DAT_PHONG WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM DAT_PHONG WHERE MaDP = %s", (ma_dp,))
            cur.execute("UPDATE PHONG SET TrangThai = 'Trống' WHERE MaPhong = 3")


def test_enhancements_profile_customers_tickets_and_shifts():
    admin_tok = _login("admin_hethong")
    letan_tok = _login("letan_cn1")
    khach_tok = _login("khach_an")

    # Profile & ticket-types & customer search & shift catalog
    prof = client.get("/api/auth/profile", headers=_headers(khach_tok))
    assert prof.status_code == 200
    assert prof.json()["detail"]["MaKH"] == 1

    custs = client.get("/api/operations/customers", params={"q": "Nguyễn"}, headers=_headers(letan_tok))
    assert custs.status_code == 200
    assert len(custs.json()) > 0

    t_types = client.get("/api/catalog/ticket-types", params={"ma_cn": 1})
    assert t_types.status_code == 200
    ticket_types = t_types.json()
    assert len(ticket_types) > 0

    shifts_cat = client.get("/api/admin/shifts-catalog", headers=_headers(admin_tok))
    assert shifts_cat.status_code == 200
    assert len(shifts_cat.json()) > 0

    staff = client.get("/api/admin/staff-list", params={"ma_cn": 1}, headers=_headers(admin_tok))
    assert staff.status_code == 200
    assert len(staff.json()) > 0

    # Tao don -> phat hanh ve QR ngay hom nay -> quet ve thanh cong
    created = client.post(
        "/api/bookings",
        json={
            "ma_phong": 3,
            "ngay_checkin": "2026-12-15",
            "ngay_checkout": "2026-12-17",
            "ghi_chu": "Test live ticket",
        },
        headers=_headers(khach_tok),
    )
    assert created.status_code == 201, created.text
    ma_dp = created.json()["MaDP"]
    ma_hd = created.json()["MaHD"]
    qr_full = created.json().get("payment_qr")
    assert qr_full and qr_full["vietqr_payload"].startswith("000201")
    assert qr_full["so_tien_chuyen"] > 0

    try:
        qr_dep = client.get(
            f"/api/invoices/{ma_hd}/payment-qr",
            params={"mode": "deposit"},
            headers=_headers(khach_tok),
        )
        assert qr_dep.status_code == 200, qr_dep.text
        assert qr_dep.json()["so_tien_chuyen"] < qr_full["so_tien_chuyen"]
        assert client.post(f"/api/bookings/{ma_dp}/confirm", headers=_headers(letan_tok)).status_code == 200
        issued = client.post(
            "/api/operations/tickets",
            json={
                "ma_dp": ma_dp,
                "ma_loai_ve": ticket_types[0]["MaLoaiVe"],
                "ngay_su_dung": date.today().isoformat(),
                "so_luong": 1,
            },
            headers=_headers(letan_tok),
        )
        assert issued.status_code == 201, issued.text
        ma_qr = issued.json()["tickets"][0]["MaQR"]

        scanned = client.post(
            "/api/operations/tickets/scan",
            json={"ma_qr": ma_qr, "ma_cn": 1},
            headers=_headers(letan_tok),
        )
        assert scanned.status_code == 200, scanned.text
        assert scanned.json()["ticket"]["TrangThai"] == "Đã sử dụng"
    finally:
        with get_cursor() as cur:
            cur.execute("DELETE FROM VE_DIEN_TU WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM CT_HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM CT_DAT_PHONG WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM DAT_PHONG WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM NHAT_KY_HOAT_DONG WHERE MaNhatKy > 1")


def test_bank_webhook_and_vietqr_decode():
    from app.config import get_settings

    settings = get_settings()
    khach_tok = _login("khach_an")
    created = client.post(
        "/api/bookings",
        json={
            "ma_phong": 3,
            "ngay_checkin": "2026-12-20",
            "ngay_checkout": "2026-12-22",
            "ghi_chu": "Test bank webhook",
        },
        headers=_headers(khach_tok),
    )
    assert created.status_code == 201, created.text
    ma_dp = created.json()["MaDP"]
    ma_hd = created.json()["MaHD"]
    qr_full = created.json()["payment_qr"]
    assert qr_full["bank_code"] == settings.bank_code
    assert qr_full["account_no"] == settings.bank_account_no

    try:
        decoded = client.post("/api/bank/decode-qr", json={"payload": qr_full["vietqr_payload"]})
        assert decoded.status_code == 200, decoded.text
        djson = decoded.json()
        assert djson["crc_valid"] is True
        assert djson["is_target_merchant"] is True
        assert djson["account_no"] == settings.bank_account_no
        assert djson["ma_hd"] == ma_hd
        assert djson["amount"] == qr_full["so_tien_chuyen"]

        # Sai API key phai bi tu choi 401
        bad_auth = client.post(
            "/api/bank/webhook",
            json={
                "account_no": settings.bank_account_no,
                "transaction_id": f"TEST-BAD-{ma_hd}",
                "amount": 100000,
                "memo": djson["memo"],
            },
            headers={"X-Bank-Api-Key": "wrong-key"},
        )
        assert bad_auth.status_code == 401

        # Thanh toan coc 30% qua webhook -> tu dong xac nhan don
        qr_dep = client.get(
            f"/api/invoices/{ma_hd}/payment-qr",
            params={"mode": "deposit"},
            headers=_headers(khach_tok),
        ).json()
        tx_dep = f"TEST-MB-DEP-{ma_hd}"
        wh_dep = client.post(
            "/api/bank/webhook",
            json={
                "bank_code": "MB",
                "account_no": settings.bank_account_no,
                "transaction_id": tx_dep,
                "amount": qr_dep["so_tien_chuyen"],
                "memo": qr_dep["noi_dung"],
                "sender_account": "999988887777",
                "sender_name": "NGUYEN VAN TEST",
            },
            headers={"X-Bank-Api-Key": settings.bank_webhook_secret},
        )
        assert wh_dep.status_code == 200, wh_dep.text
        wjson = wh_dep.json()
        assert wjson["duplicate"] is False
        assert wjson["trang_thai_hd"] == "Thanh toán một phần"
        assert wjson["auto_confirmed"] is True

        # Ban lai webhook cung transaction_id -> chong cong trung
        wh_dup = client.post(
            "/api/bank/webhook",
            json={
                "account_no": settings.bank_account_no,
                "transaction_id": tx_dep,
                "amount": qr_dep["so_tien_chuyen"],
                "memo": qr_dep["noi_dung"],
            },
            headers={"X-Bank-Api-Key": settings.bank_webhook_secret},
        )
        assert wh_dup.status_code == 200
        assert wh_dup.json()["duplicate"] is True

        # Thanh toan phan con lai -> Da thanh toan
        remaining = int(round(wjson["con_phai_tra"]))
        wh_rest = client.post(
            "/api/bank/webhook",
            json={
                "account_no": settings.bank_account_no,
                "transaction_id": f"TEST-MB-FULL-{ma_hd}",
                "amount": remaining,
                "memo": qr_dep["noi_dung"],
            },
            headers={"X-Bank-Api-Key": settings.bank_webhook_secret},
        )
        assert wh_rest.status_code == 200, wh_rest.text
        assert wh_rest.json()["trang_thai_hd"] == "Đã thanh toán"

        status_res = client.get(f"/api/invoices/{ma_hd}/payment-status", headers=_headers(khach_tok))
        assert status_res.status_code == 200
        assert status_res.json()["trang_thai_hd"] == "Đã thanh toán"
        assert status_res.json()["trang_thai_dp"] == "Đã xác nhận"
        assert status_res.json()["con_phai_tra"] == 0.0
    finally:
        with get_cursor() as cur:
            cur.execute("DELETE FROM GIAO_DICH_THANH_TOAN WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM CT_HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM CT_DAT_PHONG WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM DAT_PHONG WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM NHAT_KY_HOAT_DONG WHERE MaNhatKy > 1")


def test_holiday_and_scope_voucher_rules():
    khach_tok = _login("khach_an")
    vouchers = client.get("/api/catalog/vouchers").json()
    ks_voucher = min(
        [v for v in vouchers if v["TrangThai"] == "Hiệu lực" and v["LoaiApDung"] == "Khách sạn"],
        key=lambda x: float(x["DonHangToiThieu"]),
    )
    vc_voucher = min(
        [v for v in vouchers if v["TrangThai"] == "Hiệu lực" and v["LoaiApDung"] == "Khu vui chơi"],
        key=lambda x: float(x["DonHangToiThieu"]),
    )

    tt_res = client.get("/api/catalog/ticket-types", params={"ma_cn": 1}).json()
    ma_loai_ve = tt_res[0]["MaLoaiVe"]

    # Find an available room on both holiday and normal windows
    avail_hol = client.get(
        "/api/bookings/availability",
        params={"ma_cn": 1, "ngay_checkin": "2027-01-01", "ngay_checkout": "2027-01-03", "suc_chua": 1},
    ).json()
    ma_phong = avail_hol[0]["MaPhong"]

    hol_status = client.get(
        "/api/bookings/holiday-status",
        params={"ngay_checkin": "2027-01-01", "ngay_checkout": "2027-01-03"},
    )
    assert hol_status.status_code == 200
    assert hol_status.json()["is_holiday"] is True

    norm_status = client.get(
        "/api/bookings/holiday-status",
        params={"ngay_checkin": "2027-03-10", "ngay_checkout": "2027-03-12"},
    )
    assert norm_status.status_code == 200
    assert norm_status.json()["is_holiday"] is False

    created = []
    used_codes = []
    try:
        # 1) Holiday + hotel-only + voucher -> rejected
        r_hol_hotel = client.post(
            "/api/bookings",
            json={
                "ma_phong": ma_phong,
                "ngay_checkin": "2027-01-01",
                "ngay_checkout": "2027-01-03",
                "voucher_codes": [ks_voucher["Code"]],
            },
            headers=_headers(khach_tok),
        )
        assert r_hol_hotel.status_code == 400

        # 2) Holiday + hotel + amusement + 2 vouchers -> rejected
        r_hol_two = client.post(
            "/api/bookings",
            json={
                "ma_phong": ma_phong,
                "ngay_checkin": "2027-01-01",
                "ngay_checkout": "2027-01-03",
                "ticket_items": [{"ma_loai_ve": ma_loai_ve, "so_luong": 2}],
                "voucher_codes": [ks_voucher["Code"], vc_voucher["Code"]],
            },
            headers=_headers(khach_tok),
        )
        assert r_hol_two.status_code == 400

        # 3) Holiday + hotel + amusement + 1 voucher -> allowed
        r_hol_one = client.post(
            "/api/bookings",
            json={
                "ma_phong": ma_phong,
                "ngay_checkin": "2027-01-01",
                "ngay_checkout": "2027-01-03",
                "ticket_items": [{"ma_loai_ve": ma_loai_ve, "so_luong": 2}],
                "voucher_codes": [vc_voucher["Code"]],
            },
            headers=_headers(khach_tok),
        )
        assert r_hol_one.status_code == 201, r_hol_one.text
        created.append((r_hol_one.json()["MaDP"], r_hol_one.json()["MaHD"]))
        used_codes.append(vc_voucher["Code"])
        assert len(r_hol_one.json()["applied_vouchers"]) == 1

        # 4) Normal day + hotel-only + amusement voucher -> rejected
        r_norm_wrong = client.post(
            "/api/bookings",
            json={
                "ma_phong": ma_phong,
                "ngay_checkin": "2027-03-10",
                "ngay_checkout": "2027-03-12",
                "voucher_codes": [vc_voucher["Code"]],
            },
            headers=_headers(khach_tok),
        )
        assert r_norm_wrong.status_code == 400

        # 5) Normal day + hotel + amusement + 2 vouchers (1 KS + 1 VC) -> allowed
        r_norm_two = client.post(
            "/api/bookings",
            json={
                "ma_phong": ma_phong,
                "ngay_checkin": "2027-03-10",
                "ngay_checkout": "2027-03-12",
                "ticket_items": [{"ma_loai_ve": ma_loai_ve, "so_luong": 3}],
                "voucher_codes": [ks_voucher["Code"], vc_voucher["Code"]],
            },
            headers=_headers(khach_tok),
        )
        assert r_norm_two.status_code == 201, r_norm_two.text
        created.append((r_norm_two.json()["MaDP"], r_norm_two.json()["MaHD"]))
        used_codes.extend([ks_voucher["Code"], vc_voucher["Code"]])
        assert len(r_norm_two.json()["applied_vouchers"]) == 2
        assert r_norm_two.json()["payment_qr"] is not None
    finally:
        with get_cursor() as cur:
            for c in used_codes:
                cur.execute("UPDATE MA_GIAM_GIA SET SoLuongDaDung = GREATEST(SoLuongDaDung - 1, 0) WHERE Code = %s", (c,))
            for ma_dp, ma_hd in created:
                cur.execute("DELETE FROM VE_DIEN_TU WHERE MaDP = %s", (ma_dp,))
                cur.execute("DELETE FROM GIAO_DICH_THANH_TOAN WHERE MaHD = %s", (ma_hd,))
                cur.execute("DELETE FROM CT_HOA_DON WHERE MaHD = %s", (ma_hd,))
                cur.execute("DELETE FROM HOA_DON WHERE MaHD = %s", (ma_hd,))
                cur.execute("DELETE FROM CT_DAT_PHONG WHERE MaDP = %s", (ma_dp,))
                cur.execute("DELETE FROM DAT_PHONG WHERE MaDP = %s", (ma_dp,))


def test_admin_cancel_requires_customer_otp():
    khach_tok = _login("khach_an")
    admin_tok = _login("admin_hethong")

    avail = client.get(
        "/api/bookings/availability",
        params={"ma_cn": 1, "ngay_checkin": "2027-04-10", "ngay_checkout": "2027-04-12", "suc_chua": 1},
    ).json()
    ma_phong = avail[0]["MaPhong"]

    bk = client.post(
        "/api/bookings",
        json={"ma_phong": ma_phong, "ngay_checkin": "2027-04-10", "ngay_checkout": "2027-04-12"},
        headers=_headers(khach_tok),
    )
    assert bk.status_code == 201, bk.text
    ma_dp = bk.json()["MaDP"]
    ma_hd = bk.json()["MaHD"]

    try:
        # Admin cannot cancel without OTP
        c_no_otp = client.post(
            f"/api/bookings/{ma_dp}/cancel",
            json={"ly_do": "Khách yêu cầu hủy"},
            headers=_headers(admin_tok),
        )
        assert c_no_otp.status_code == 400

        # Admin sends OTP to customer's notification inbox
        otp_req = client.post(
            f"/api/bookings/{ma_dp}/cancel-otp",
            json={"ly_do": "Khách yêu cầu hủy"},
            headers=_headers(admin_tok),
        )
        assert otp_req.status_code == 200, otp_req.text
        assert "OtpCode" not in otp_req.json()

        # Customer reads OTP from notifications
        notif_res = client.get("/api/notifications", headers=_headers(khach_tok))
        assert notif_res.status_code == 200
        otp_items = [x for x in notif_res.json()["items"] if x["MaDP"] == ma_dp and x["LoaiTB"] == "CANCEL_OTP"]
        assert len(otp_items) == 1
        real_otp = otp_items[0]["OtpCode"]
        assert real_otp and len(real_otp) == 6

        # Wrong OTP fails
        wrong_otp = "000000" if real_otp != "000000" else "999999"
        c_bad = client.post(
            f"/api/bookings/{ma_dp}/cancel",
            json={"ly_do": "Khách yêu cầu hủy", "otp_code": wrong_otp},
            headers=_headers(admin_tok),
        )
        assert c_bad.status_code == 400

        # Correct OTP succeeds
        c_ok = client.post(
            f"/api/bookings/{ma_dp}/cancel",
            json={"ly_do": "Khách yêu cầu hủy", "otp_code": real_otp},
            headers=_headers(admin_tok),
        )
        assert c_ok.status_code == 200, c_ok.text
    finally:
        with get_cursor() as cur:
            cur.execute("DELETE FROM THONG_BAO_KHACH_HANG WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM CT_HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM CT_DAT_PHONG WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM DAT_PHONG WHERE MaDP = %s", (ma_dp,))


def test_customer_and_staff_service_orders_and_customer_tickets():
    khach_tok = _login("khach_an")
    letan_tok = _login("letan_cn1")

    avail = client.get(
        "/api/bookings/availability",
        params={"ma_cn": 1, "ngay_checkin": "2027-05-10", "ngay_checkout": "2027-05-12", "suc_chua": 1},
    ).json()
    ma_phong = avail[0]["MaPhong"]

    services = [s for s in client.get("/api/catalog/services", params={"ma_cn": 1}).json() if s["TrangThai"] == "Đang cung cấp"]
    ma_dv = services[0]["MaDV"]
    ticket_types = client.get("/api/catalog/ticket-types", params={"ma_cn": 1}).json()
    ma_loai_ve = ticket_types[0]["MaLoaiVe"]

    bk = client.post(
        "/api/bookings",
        json={"ma_phong": ma_phong, "ngay_checkin": "2027-05-10", "ngay_checkout": "2027-05-12"},
        headers=_headers(khach_tok),
    )
    assert bk.status_code == 201, bk.text
    ma_dp = bk.json()["MaDP"]
    ma_hd = bk.json()["MaHD"]

    try:
        # 1) Customer buys ticket directly -> receives payment_qr
        tk_res = client.post(
            "/api/operations/tickets",
            json={"ma_dp": ma_dp, "ma_loai_ve": ma_loai_ve, "ngay_su_dung": "2027-05-10", "so_luong": 1},
            headers=_headers(khach_tok),
        )
        assert tk_res.status_code == 201, tk_res.text
        assert len(tk_res.json()["tickets"]) == 1
        assert tk_res.json()["payment_qr"] is not None

        # 2) Customer orders service directly -> immediate + payment_qr
        cus_svc = client.post(
            "/api/operations/service-orders",
            json={"ma_dp": ma_dp, "ma_cn": 1, "ma_dv": ma_dv, "so_luong": 1},
            headers=_headers(khach_tok),
        )
        assert cus_svc.status_code == 201, cus_svc.text
        assert cus_svc.json()["mode"] == "direct_customer"
        assert cus_svc.json()["payment_qr"] is not None

        # 3) Receptionist proposes service -> sends notification to customer, does not charge yet
        staff_svc = client.post(
            "/api/operations/service-orders",
            json={"ma_dp": ma_dp, "ma_cn": 1, "ma_dv": ma_dv, "so_luong": 2, "ghi_chu": "Giao buổi tối"},
            headers=_headers(letan_tok),
        )
        assert staff_svc.status_code == 201, staff_svc.text
        assert staff_svc.json()["mode"] == "pending_customer_confirm"
        ma_tb = staff_svc.json()["MaTB"]

        # 4) Customer confirms notification -> recorded + returns payment_qr
        resp = client.post(
            f"/api/notifications/{ma_tb}/respond",
            json={"action": "confirm"},
            headers=_headers(khach_tok),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["TrangThai"] == "Đã xác nhận"
        assert resp.json()["payment_qr"] is not None
    finally:
        with get_cursor() as cur:
            cur.execute("DELETE FROM THONG_BAO_KHACH_HANG WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM SU_DUNG_DV WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM VE_DIEN_TU WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM CT_HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM HOA_DON WHERE MaHD = %s", (ma_hd,))
            cur.execute("DELETE FROM CT_DAT_PHONG WHERE MaDP = %s", (ma_dp,))
            cur.execute("DELETE FROM DAT_PHONG WHERE MaDP = %s", (ma_dp,))
