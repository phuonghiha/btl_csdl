from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..db import fetch_one, get_cursor
from ..security import (
    create_access_token,
    get_current_user,
    hash_password,
    load_user_profile,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Xác thực & Tài khoản"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=60)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=60)
    password: str = Field(..., min_length=6, max_length=128)
    ho_ten: str = Field(..., min_length=2, max_length=160)
    cccd: str = Field(..., min_length=9, max_length=25)
    sdt: str = Field(..., min_length=8, max_length=20)
    email: str | None = Field(default=None, max_length=160)
    dia_chi: str | None = Field(default=None, max_length=300)


class UpdateProfileRequest(BaseModel):
    ho_ten: str | None = Field(default=None, min_length=2, max_length=160)
    sdt: str | None = Field(default=None, min_length=8, max_length=20)
    email: str | None = Field(default=None, max_length=160)
    dia_chi: str | None = Field(default=None, max_length=300)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


@router.post("/login")
def login(body: LoginRequest):
    row = fetch_one(
        "SELECT MaTK, TenDangNhap, MatKhauHash, TrangThai FROM TAI_KHOAN WHERE TenDangNhap = %s",
        (body.username.strip(),),
    )
    if not row or not verify_password(body.password, row["MatKhauHash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai tên đăng nhập hoặc mật khẩu",
        )
    if row["TrangThai"] != "Hoạt động":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tài khoản đang ở trạng thái: {row['TrangThai']}",
        )

    profile = load_user_profile(row["MaTK"])
    token = create_access_token(row["MaTK"], row["TenDangNhap"])
    return {"access_token": token, "token_type": "bearer", "user": profile}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_customer(body: RegisterRequest):
    username = body.username.strip()
    existing_tk = fetch_one("SELECT MaTK FROM TAI_KHOAN WHERE TenDangNhap = %s", (username,))
    if existing_tk:
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")

    existing_cccd = fetch_one("SELECT MaKH FROM KHACH_HANG WHERE CCCD = %s", (body.cccd.strip(),))
    if existing_cccd:
        raise HTTPException(status_code=400, detail="CCCD đã được đăng ký trước đó")

    pw_hash = hash_password(body.password)

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
            INSERT INTO TAI_KHOAN (TenDangNhap, MatKhauHash, Email, TrangThai, MaNV, MaKH)
            VALUES (%s, %s, %s, 'Hoạt động', NULL, %s)
            """,
            (username, pw_hash, body.email, ma_kh),
        )
        ma_tk = cur.lastrowid

        cur.execute(
            """
            INSERT INTO TAI_KHOAN_VAI_TRO (MaTK, MaVaiTro)
            SELECT %s, MaVaiTro FROM VAI_TRO WHERE MaCode = 'KHACH_HANG'
            """,
            (ma_tk,),
        )

    profile = load_user_profile(ma_tk)
    token = create_access_token(ma_tk, username)
    return {"access_token": token, "token_type": "bearer", "user": profile}


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return user


@router.get("/profile")
def get_profile(user: dict = Depends(get_current_user)):
    detail = {}
    if user["MaKH"] is not None:
        detail = fetch_one(
            "SELECT MaKH, HoTen, CCCD, SDT, Email, DiaChi FROM KHACH_HANG WHERE MaKH = %s",
            (user["MaKH"],),
        ) or {}
    elif user["MaNV"] is not None:
        detail = fetch_one(
            "SELECT MaNV, MaCN, HoTen, SDT, Email, ChucVu, NgayVaoLam FROM NHAN_VIEN WHERE MaNV = %s",
            (user["MaNV"],),
        ) or {}
    return {**user, "detail": detail}


@router.patch("/profile")
def update_profile(body: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    if "PROFILE.UPDATE_SELF" not in user["permissions"] and not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Không có quyền cập nhật hồ sơ cá nhân")

    email_val = body.email.strip() if body.email else None
    with get_cursor(autocommit=False) as cur:
        if email_val is not None:
            cur.execute("UPDATE TAI_KHOAN SET Email = %s WHERE MaTK = %s", (email_val, user["MaTK"]))

        if user["MaKH"] is not None:
            cur.execute(
                """
                UPDATE KHACH_HANG
                SET HoTen = COALESCE(%s, HoTen),
                    SDT = COALESCE(%s, SDT),
                    Email = COALESCE(%s, Email),
                    DiaChi = COALESCE(%s, DiaChi)
                WHERE MaKH = %s
                """,
                (
                    body.ho_ten.strip() if body.ho_ten else None,
                    body.sdt.strip() if body.sdt else None,
                    email_val,
                    body.dia_chi.strip() if body.dia_chi is not None else None,
                    user["MaKH"],
                ),
            )
        elif user["MaNV"] is not None:
            cur.execute(
                """
                UPDATE NHAN_VIEN
                SET SDT = COALESCE(%s, SDT),
                    Email = COALESCE(%s, Email)
                WHERE MaNV = %s
                """,
                (
                    body.sdt.strip() if body.sdt else None,
                    email_val,
                    user["MaNV"],
                ),
            )

        cur.execute(
            """
            INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, LyDo)
            VALUES (%s, 'CAP_NHAT_HO_SO', 'TAI_KHOAN', %s, 'Người dùng tự cập nhật thông tin liên hệ')
            """,
            (user["MaTK"], str(user["MaTK"])),
        )

    return {"message": "Đã cập nhật hồ sơ cá nhân", "user": load_user_profile(user["MaTK"])}


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    row = fetch_one("SELECT MatKhauHash FROM TAI_KHOAN WHERE MaTK = %s", (user["MaTK"],))
    if not row or not verify_password(body.current_password, row["MatKhauHash"]):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không chính xác")

    new_hash = hash_password(body.new_password)
    with get_cursor(autocommit=False) as cur:
        cur.execute("UPDATE TAI_KHOAN SET MatKhauHash = %s WHERE MaTK = %s", (new_hash, user["MaTK"]))
        cur.execute(
            """
            INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, LyDo)
            VALUES (%s, 'DOI_MAT_KHAU', 'TAI_KHOAN', %s, 'Đổi mật khẩu cá nhân')
            """,
            (user["MaTK"], str(user["MaTK"])),
        )
    return {"message": "Đổi mật khẩu thành công"}
