from contextlib import asynccontextmanager

import pymysql
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from .config import get_settings
from .db import get_cursor
from .routers import admin, auth, bank_webhook, bookings, catalog, finance, notifications, operations

settings = get_settings()


def ensure_schema_extensions() -> None:
    """Idempotent runtime migration for voucher scope and customer notifications."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'MA_GIAM_GIA'
              AND COLUMN_NAME = 'LoaiApDung'
            """
        )
        has_col = (cur.fetchone() or {}).get("cnt", 0)
        if not has_col:
            cur.execute(
                """
                ALTER TABLE MA_GIAM_GIA
                ADD COLUMN LoaiApDung ENUM('Khách sạn', 'Khu vui chơi')
                NOT NULL DEFAULT 'Khách sạn' AFTER Code
                """
            )
            cur.execute(
                """
                UPDATE MA_GIAM_GIA
                SET LoaiApDung = 'Khu vui chơi'
                WHERE Code LIKE 'WONDERS%'
                   OR Code LIKE 'DISCOVERY%'
                   OR Code LIKE 'VINPEARL%'
                """
            )
            cur.execute(
                """
                UPDATE MA_GIAM_GIA
                SET LoaiApDung = 'Khách sạn'
                WHERE Code NOT LIKE 'WONDERS%'
                  AND Code NOT LIKE 'DISCOVERY%'
                  AND Code NOT LIKE 'VINPEARL%'
                """
            )
        cur.execute(
            """
            UPDATE MA_GIAM_GIA
            SET NgayKetThuc = '2028-12-31'
            WHERE NgayKetThuc < '2026-12-31'
              AND TrangThai = 'Hiệu lực'
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS THONG_BAO_KHACH_HANG (
                MaTB BIGINT AUTO_INCREMENT PRIMARY KEY,
                MaKH INT NOT NULL,
                MaDP INT NOT NULL,
                LoaiTB ENUM('CANCEL_OTP', 'SERVICE_CONFIRM', 'TICKET_CONFIRM', 'INFO') NOT NULL,
                TieuDe VARCHAR(200) NOT NULL,
                NoiDung TEXT NOT NULL,
                OtpCode VARCHAR(12) NULL,
                DuLieuJson JSON NULL,
                TrangThai ENUM('Chờ xác nhận', 'Đã xác nhận', 'Đã từ chối', 'Hết hạn') NOT NULL DEFAULT 'Chờ xác nhận',
                NguoiGuiMaTK BIGINT NULL,
                ThoiGianTao DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                HetHanLuc DATETIME NULL,
                ThoiGianPhanHoi DATETIME NULL,
                INDEX IDX_TB_KH_TT (MaKH, TrangThai, ThoiGianTao),
                INDEX IDX_TB_DP_LOAI (MaDP, LoaiTB, TrangThai),
                FOREIGN KEY (MaKH) REFERENCES KHACH_HANG(MaKH),
                FOREIGN KEY (MaDP) REFERENCES DAT_PHONG(MaDP),
                FOREIGN KEY (NguoiGuiMaTK) REFERENCES TAI_KHOAN(MaTK)
            ) ENGINE=InnoDB
            """
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_schema_extensions()
    yield


app = FastAPI(
    title="API Quản lý Chuỗi Khách sạn",
    version="1.0.0",
    description="Backend FastAPI kết nối trực tiếp MySQL quan_ly_khach_san (VIEW, FUNCTION, STORED PROCEDURE, TRIGGER, RBAC).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(pymysql.err.OperationalError)
async def mysql_signal_handler(_: Request, exc: pymysql.err.OperationalError):
    code = exc.args[0] if exc.args else 500
    msg = exc.args[1] if len(exc.args) > 1 else str(exc)
    # 1644: SIGNAL SQLSTATE '45000' tu trigger / stored procedure nghiep vu
    # 3819: CHECK constraint violated, 1062: Duplicate entry
    if code in (1644, 3819):
        return JSONResponse(status_code=400, content={"detail": msg})
    return JSONResponse(status_code=500, content={"detail": f"Lỗi cơ sở dữ liệu ({code}): {msg}"})


@app.exception_handler(pymysql.err.IntegrityError)
async def mysql_integrity_handler(_: Request, exc: pymysql.err.IntegrityError):
    code = exc.args[0] if exc.args else 400
    msg = exc.args[1] if len(exc.args) > 1 else str(exc)
    if code == 1062:
        return JSONResponse(status_code=409, content={"detail": f"Dữ liệu bị trùng lặp: {msg}"})
    return JSONResponse(status_code=400, content={"detail": f"Vi phạm ràng buộc dữ liệu ({code}): {msg}"})


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/docs")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "database": settings.mysql_database}


app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(bookings.router)
app.include_router(operations.router)
app.include_router(finance.router)
app.include_router(admin.router)
app.include_router(bank_webhook.router)
app.include_router(notifications.router)
