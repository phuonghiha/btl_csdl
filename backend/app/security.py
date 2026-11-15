import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .db import get_cursor

bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    """Hash password with PBKDF2-HMAC-SHA256 for newly created accounts."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(plain: str, stored_hash: str) -> bool:
    """Verify both PBKDF2 hashes and demo SHA-256 hex hashes from 09_seed_demo_accounts.sql."""
    if stored_hash.startswith("pbkdf2_sha256$"):
        parts = stored_hash.split("$", 2)
        if len(parts) != 3:
            return False
        _, salt, expected = parts
        digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
        return hmac.compare_digest(digest, expected)
    # Fallback for 64-char SHA2(..., 256) hex seeded in demo SQL
    sha_hex = hashlib.sha256(plain.encode("utf-8")).hexdigest()
    return hmac.compare_digest(sha_hex.lower(), stored_hash.lower())


def create_access_token(user_id: int, username: str) -> str:
    cfg = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=cfg.jwt_expire_minutes),
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm="HS256")


def load_user_profile(ma_tk: int) -> dict[str, Any] | None:
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT tk.MaTK, tk.TenDangNhap, tk.Email, tk.TrangThai, tk.MaNV, tk.MaKH,
                   nv.HoTen AS TenNhanVien, nv.MaCN AS MaCN_NhanVien, nv.ChucVu,
                   kh.HoTen AS TenKhachHang, kh.SDT AS SdtKhachHang
            FROM TAI_KHOAN tk
            LEFT JOIN NHAN_VIEN nv ON nv.MaNV = tk.MaNV
            LEFT JOIN KHACH_HANG kh ON kh.MaKH = tk.MaKH
            WHERE tk.MaTK = %s
            """,
            (ma_tk,),
        )
        account = cur.fetchone()
        if not account:
            return None

        cur.execute(
            """
            SELECT vt.MaCode, vt.TenVaiTro
            FROM TAI_KHOAN_VAI_TRO tvt
            JOIN VAI_TRO vt ON vt.MaVaiTro = tvt.MaVaiTro
            WHERE tvt.MaTK = %s
            """,
            (ma_tk,),
        )
        roles = list(cur.fetchall())

        cur.execute(
            """
            SELECT DISTINCT q.MaCode
            FROM TAI_KHOAN_VAI_TRO tvt
            JOIN VAI_TRO_QUYEN vtq ON vtq.MaVaiTro = tvt.MaVaiTro
            JOIN QUYEN q ON q.MaQuyen = vtq.MaQuyen
            WHERE tvt.MaTK = %s
            """,
            (ma_tk,),
        )
        perms = list(cur.fetchall())

        cur.execute(
            """
            SELECT pc.MaCN, cn.TenCN, pc.VaiTroTaiCN
            FROM PHAN_CONG_CHI_NHANH pc
            JOIN CHI_NHANH cn ON cn.MaCN = pc.MaCN
            WHERE pc.MaTK = %s
              AND (pc.NgayKetThuc IS NULL OR pc.NgayKetThuc >= CURRENT_DATE())
            """,
            (ma_tk,),
        )
        branches = list(cur.fetchall())

    account["roles"] = [r["MaCode"] for r in roles]
    account["role_names"] = [r["TenVaiTro"] for r in roles]
    account["permissions"] = [p["MaCode"] for p in perms]
    account["branches"] = branches
    account["branch_ids"] = [b["MaCN"] for b in branches]
    account["is_admin"] = "ADMIN" in account["roles"] or "SYSTEM.ALL" in account["permissions"]
    return account


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any]:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chưa đăng nhập")
    cfg = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, cfg.jwt_secret, algorithms=["HS256"])
        ma_tk = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token không hợp lệ hoặc đã hết hạn")

    user = load_user_profile(ma_tk)
    if not user or user["TrangThai"] != "Hoạt động":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tài khoản không tồn tại hoặc đang bị khóa")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict[str, Any] | None:
    if not credentials:
        return None
    cfg = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, cfg.jwt_secret, algorithms=["HS256"])
        ma_tk = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    user = load_user_profile(ma_tk)
    if not user or user["TrangThai"] != "Hoạt động":
        return None
    return user


def require_permission(permission_code: str):
    def _dep(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if user["is_admin"] or permission_code in user["permissions"]:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Bạn không có quyền '{permission_code}'",
        )

    return _dep


def ensure_branch_access(user: dict[str, Any], ma_cn: int) -> None:
    if user["is_admin"]:
        return
    if ma_cn not in user["branch_ids"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không được phân công thao tác tại chi nhánh này",
        )
