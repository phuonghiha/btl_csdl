-- =============================================================================
-- 12_notifications_and_voucher_scope.sql
-- Bo sung:
--   1. Phan loai pham vi ap dung voucher (Khach san / Khu vui choi) & gia han demo
--   2. Bang THONG_BAO_KHACH_HANG phuc vu OTP huy don tu Admin/Le tan
--      va xac nhan dich vu do nhan vien dat ho khach hang.
-- =============================================================================

USE quan_ly_khach_san;
SET NAMES utf8mb4;

-- 1. Them cot LoaiApDung cho MA_GIAM_GIA (neu chua co)
SET @has_col := (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'MA_GIAM_GIA'
      AND COLUMN_NAME = 'LoaiApDung'
);
SET @sql_col := IF(
    @has_col = 0,
    "ALTER TABLE MA_GIAM_GIA ADD COLUMN LoaiApDung ENUM('Khách sạn', 'Khu vui chơi') NOT NULL DEFAULT 'Khách sạn' AFTER Code",
    'SELECT 1'
);
PREPARE stmt FROM @sql_col;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Phan loai cac voucher mau theo ten goi nghiep vu
UPDATE MA_GIAM_GIA
SET LoaiApDung = 'Khu vui chơi'
WHERE Code LIKE 'WONDERS%'
   OR Code LIKE 'DISCOVERY%'
   OR Code LIKE 'VINPEARL%';

UPDATE MA_GIAM_GIA
SET LoaiApDung = 'Khách sạn'
WHERE Code NOT LIKE 'WONDERS%'
  AND Code NOT LIKE 'DISCOVERY%'
  AND Code NOT LIKE 'VINPEARL%';

-- Gia han hieu luc cac voucher mau cho giai doan 2026-2028
UPDATE MA_GIAM_GIA
SET NgayKetThuc = '2028-12-31'
WHERE NgayKetThuc < '2026-12-31'
  AND TrangThai = 'Hiệu lực';

-- 2. Bang thong bao & xac nhan cua khach hang
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
) ENGINE=InnoDB;
