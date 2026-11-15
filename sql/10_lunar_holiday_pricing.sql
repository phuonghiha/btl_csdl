-- =============================================================================
-- 10_lunar_holiday_pricing.sql
-- Bo sung bang quy doi ngay le am lich sang duong lich cho BANG_GIA (LE02, LE03)
-- va nang cap fn_gia_phong_theo_ngay + bo sung fn_tinh_tien_phong_khoang_ngay.
-- Yeu cau: da chay 01_schema.sql, 06_import_csv.sql, 07_views_and_procedures.sql
-- =============================================================================

USE quan_ly_khach_san;
SET NAMES utf8mb4;

-- Bang quy doi cac su kien le am lich trong BANG_GIA sang khoang ngay duong lich theo nam
CREATE TABLE IF NOT EXISTS QUY_DOI_LE_AM_LICH (
    MaSuKienLe VARCHAR(30) NOT NULL,
    Nam INT NOT NULL,
    TenSuKien VARCHAR(150) NOT NULL,
    NgayBatDauDuong DATE NOT NULL,
    NgayKetThucDuong DATE NOT NULL,
    PRIMARY KEY (MaSuKienLe, Nam),
    INDEX IDX_QUYDOI_LE_NGAY (NgayBatDauDuong, NgayKetThucDuong),
    CHECK (NgayKetThucDuong >= NgayBatDauDuong)
) ENGINE=InnoDB;

-- Du lieu quy doi chinh xac giai doan 2024 - 2028 cho LE02 (mung 1-9 thang Gieng AL)
-- va LE03 (mung 10 thang 3 AL - Gio To Hung Vuong)
INSERT INTO QUY_DOI_LE_AM_LICH (MaSuKienLe, Nam, TenSuKien, NgayBatDauDuong, NgayKetThucDuong) VALUES
('LE02', 2024, 'Tết Nguyên Đán (Mùng 1–Mùng 9 tháng Giêng Âm lịch)', '2024-02-10', '2024-02-18'),
('LE02', 2025, 'Tết Nguyên Đán (Mùng 1–Mùng 9 tháng Giêng Âm lịch)', '2025-01-29', '2025-02-06'),
('LE02', 2026, 'Tết Nguyên Đán (Mùng 1–Mùng 9 tháng Giêng Âm lịch)', '2026-02-17', '2026-02-25'),
('LE02', 2027, 'Tết Nguyên Đán (Mùng 1–Mùng 9 tháng Giêng Âm lịch)', '2027-02-06', '2027-02-14'),
('LE02', 2028, 'Tết Nguyên Đán (Mùng 1–Mùng 9 tháng Giêng Âm lịch)', '2028-01-26', '2028-02-03'),
('LE03', 2024, 'Giỗ Tổ Hùng Vương (10 tháng 3 Âm lịch)', '2024-04-18', '2024-04-18'),
('LE03', 2025, 'Giỗ Tổ Hùng Vương (10 tháng 3 Âm lịch)', '2025-04-07', '2025-04-07'),
('LE03', 2026, 'Giỗ Tổ Hùng Vương (10 tháng 3 Âm lịch)', '2026-04-26', '2026-04-26'),
('LE03', 2027, 'Giỗ Tổ Hùng Vương (10 tháng 3 Âm lịch)', '2027-04-16', '2027-04-16'),
('LE03', 2028, 'Giỗ Tổ Hùng Vương (10 tháng 3 Âm lịch)', '2028-04-04', '2028-04-04')
AS new_row
ON DUPLICATE KEY UPDATE
    TenSuKien = new_row.TenSuKien,
    NgayBatDauDuong = new_row.NgayBatDauDuong,
    NgayKetThucDuong = new_row.NgayKetThucDuong;

DELIMITER $$

-- Nang cap ham tra gia phong 1 dem:
--   1. Uu tien le am lich (tra qua QUY_DOI_LE_AM_LICH)
--   2. Uu tien tiep theo la le duong lich co dinh (MM-DD)
--   3. Cuoi cung la gia theo mua (MM-DD, co ho tro mua vat qua nam va ngay 29/02)
DROP FUNCTION IF EXISTS fn_gia_phong_theo_ngay$$
CREATE FUNCTION fn_gia_phong_theo_ngay(
    p_MaLP VARCHAR(10),
    p_Ngay DATE
) RETURNS DECIMAL(14,2)
READS SQL DATA
BEGIN
    DECLARE v_mmdd CHAR(5);
    DECLARE v_Gia DECIMAL(14,2) DEFAULT NULL;

    -- 1. Kiem tra le am lich trong bang quy doi
    SELECT bg.GiaPhong INTO v_Gia
    FROM QUY_DOI_LE_AM_LICH qd
    JOIN BANG_GIA bg ON bg.MaSuKienLe = qd.MaSuKienLe
    WHERE bg.MaLP = p_MaLP
      AND p_Ngay BETWEEN qd.NgayBatDauDuong AND qd.NgayKetThucDuong
    ORDER BY bg.MaBG
    LIMIT 1;

    IF v_Gia IS NOT NULL THEN
        RETURN v_Gia;
    END IF;

    -- 2 & 3. Kiem tra le duong lich co dinh MM-DD, sau do den gia mua MM-DD
    SET v_mmdd = DATE_FORMAT(p_Ngay, '%m-%d');

    SELECT bg.GiaPhong INTO v_Gia
    FROM BANG_GIA bg
    WHERE bg.MaLP = p_MaLP
      AND bg.NgayBD REGEXP '^[0-9]{2}-[0-9]{2}$'
      AND bg.NgayKT REGEXP '^[0-9]{2}-[0-9]{2}$'
      AND (
          (bg.NgayBD <= bg.NgayKT AND v_mmdd BETWEEN bg.NgayBD AND bg.NgayKT)
          OR (bg.NgayBD > bg.NgayKT AND (v_mmdd >= bg.NgayBD OR v_mmdd <= bg.NgayKT))
      )
    ORDER BY (CASE WHEN bg.MaSuKienLe <> 'Không' THEN 0 ELSE 1 END), bg.MaBG
    LIMIT 1;

    IF v_Gia IS NULL AND v_mmdd = '02-29' THEN
        SELECT bg.GiaPhong INTO v_Gia
        FROM BANG_GIA bg
        WHERE bg.MaLP = p_MaLP AND bg.MaMua = 'M01' AND bg.MaSuKienLe = 'Không'
        LIMIT 1;
    END IF;

    RETURN v_Gia;
END$$

-- Ham tinh tong tien phong tung dem cho ca khoang ngay (xu ly truong hop ky luu tru
-- co dem roi vao ngay thuong va dem roi vao ngay le)
DROP FUNCTION IF EXISTS fn_tinh_tien_phong_khoang_ngay$$
CREATE FUNCTION fn_tinh_tien_phong_khoang_ngay(
    p_MaLP VARCHAR(10),
    p_NgayCheckIn DATE,
    p_NgayCheckOut DATE
) RETURNS DECIMAL(16,2)
READS SQL DATA
BEGIN
    DECLARE v_Ngay DATE;
    DECLARE v_Tong DECIMAL(16,2) DEFAULT 0;
    DECLARE v_GiaDem DECIMAL(14,2);

    IF p_NgayCheckOut <= p_NgayCheckIn THEN
        RETURN 0;
    END IF;

    SET v_Ngay = p_NgayCheckIn;
    WHILE v_Ngay < p_NgayCheckOut DO
        SET v_GiaDem = fn_gia_phong_theo_ngay(p_MaLP, v_Ngay);
        IF v_GiaDem IS NULL THEN
            RETURN NULL;
        END IF;
        SET v_Tong = v_Tong + v_GiaDem;
        SET v_Ngay = DATE_ADD(v_Ngay, INTERVAL 1 DAY);
    END WHILE;

    RETURN v_Tong;
END$$

DELIMITER ;

-- Kiem thu nhanh tren cac moc ngay am lich, duong lich va ky nghi giao thoa mua/le
SELECT
    fn_gia_phong_theo_ngay('LP001', '2025-01-29') AS GiaLP001_Tet2025_LE02,
    fn_gia_phong_theo_ngay('LP001', '2025-04-07') AS GiaLP001_GioTo2025_LE03,
    fn_gia_phong_theo_ngay('LP001', '2026-02-17') AS GiaLP001_Tet2026_LE02,
    fn_gia_phong_theo_ngay('LP001', '2026-04-26') AS GiaLP001_GioTo2026_LE03,
    fn_gia_phong_theo_ngay('LP001', '2025-02-15') AS GiaLP001_NgayThuongMuaDong,
    fn_tinh_tien_phong_khoang_ngay('LP001', '2025-01-28', '2025-01-31') AS Tong3Dem_1Thuong_2Tet;
