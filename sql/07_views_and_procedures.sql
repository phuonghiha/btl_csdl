-- =============================================================================
-- 07_views_and_procedures.sql
-- Cac VIEW bao cao, FUNCTION tinh gia va STORED PROCEDURE nghiep vu (MySQL 8.0+)
-- Yeu cau: da chay 01_schema.sql, 06_import_csv.sql, 02_seed_rbac.sql, 03_triggers.sql
-- =============================================================================

USE quan_ly_khach_san;
SET NAMES utf8mb4;

-- =============================================================================
-- PHAN 1: CAC VIEW BAO CAO VA TRA CUU
-- =============================================================================

-- 1.1. Doanh thu theo chi nhanh va thang (tach DISTINCT MaDP-MaCN de tranh cong trung
--      HOA_DON.TongTien doi voi cac don dat nhieu phong).
CREATE OR REPLACE VIEW vw_doanh_thu_chi_nhanh AS
SELECT
    cn.MaCN,
    cn.TenCN,
    DATE_FORMAT(hd.NgayLap, '%Y-%m') AS ThangLap,
    COUNT(DISTINCT hd.MaHD) AS SoHoaDon,
    COALESCE(SUM(hd.TongTien), 0) AS TongTienHoaDon,
    COALESCE(SUM(gd_ok.TongDaThu), 0) AS TongTienDaThu,
    COALESCE(SUM(hd.TongTien), 0) - COALESCE(SUM(gd_ok.TongDaThu), 0) AS CongNoConLai
FROM (
    SELECT DISTINCT c.MaDP, p.MaCN
    FROM CT_DAT_PHONG c
    JOIN PHONG p ON p.MaPhong = c.MaPhong
) dp_cn
JOIN CHI_NHANH cn ON cn.MaCN = dp_cn.MaCN
JOIN HOA_DON hd ON hd.MaDP = dp_cn.MaDP
LEFT JOIN (
    SELECT MaHD, SUM(SoTien) AS TongDaThu
    FROM GIAO_DICH_THANH_TOAN
    WHERE TrangThai = 'Thành công'
    GROUP BY MaHD
) gd_ok ON gd_ok.MaHD = hd.MaHD
GROUP BY cn.MaCN, cn.TenCN, DATE_FORMAT(hd.NgayLap, '%Y-%m');

-- 1.2. Tinh trang va cong suat phong hien tai theo chi nhanh
CREATE OR REPLACE VIEW vw_cong_suat_phong_chi_nhanh AS
SELECT
    cn.MaCN,
    cn.TenCN,
    COUNT(p.MaPhong) AS TongSoPhong,
    SUM(CASE WHEN p.TrangThai = 'Trống' THEN 1 ELSE 0 END) AS SoPhongTrong,
    SUM(CASE WHEN p.TrangThai = 'Đang sử dụng' THEN 1 ELSE 0 END) AS SoPhongDangSuDung,
    SUM(CASE WHEN p.TrangThai = 'Đã sẵn sàng' THEN 1 ELSE 0 END) AS SoPhongSanSang,
    SUM(CASE WHEN p.TrangThai = 'Bảo trì' THEN 1 ELSE 0 END) AS SoPhongBaoTri,
    ROUND(
        100.0 * SUM(CASE WHEN p.TrangThai = 'Đang sử dụng' THEN 1 ELSE 0 END)
        / NULLIF(COUNT(p.MaPhong), 0),
        2
    ) AS TyLeDangSuDungPct
FROM CHI_NHANH cn
LEFT JOIN PHONG p ON p.MaCN = cn.MaCN
GROUP BY cn.MaCN, cn.TenCN;

-- 1.3. Chi tiet dat phong day du (phuc vu le tan va khach hang tra cuu)
CREATE OR REPLACE VIEW vw_chi_tiet_dat_phong_day_du AS
SELECT
    dp.MaDP,
    dp.NgayDat,
    dp.TrangThai AS TrangThaiDatPhong,
    kh.MaKH,
    kh.HoTen AS TenKhachHang,
    kh.SDT AS SdtKhachHang,
    cn.MaCN,
    cn.TenCN,
    p.MaPhong,
    p.SoPhong,
    p.Tang,
    lp.MaLP,
    lp.TenLP,
    lp.SucChua,
    ctdp.MaCTDP,
    ctdp.NgayCheckIn,
    ctdp.NgayCheckOut,
    DATEDIFF(ctdp.NgayCheckOut, ctdp.NgayCheckIn) AS SoDem,
    ctdp.GiaThoaThuan,
    hd.MaHD,
    hd.TongTien AS TongTienHoaDon,
    hd.TienCoc,
    hd.TrangThai AS TrangThaiHoaDon
FROM DAT_PHONG dp
JOIN KHACH_HANG kh ON kh.MaKH = dp.MaKH
JOIN CT_DAT_PHONG ctdp ON ctdp.MaDP = dp.MaDP
JOIN PHONG p ON p.MaPhong = ctdp.MaPhong
JOIN CHI_NHANH cn ON cn.MaCN = p.MaCN
JOIN LOAI_PHONG lp ON lp.MaLP = p.MaLP
LEFT JOIN HOA_DON hd ON hd.MaDP = dp.MaDP;

-- 1.4. Thong ke luot su dung va doanh thu dich vu theo chi nhanh
CREATE OR REPLACE VIEW vw_su_dung_dich_vu_chi_tiet AS
SELECT
    cn.MaCN,
    cn.TenCN,
    dv.MaDV,
    dv.TenDV,
    dv.LoaiDV,
    COUNT(sd.MaSD) AS SoLuotSuDung,
    COALESCE(SUM(sd.SoLuong), 0) AS TongSoLuong,
    COALESCE(SUM(sd.SoLuong * sd.DonGiaTaiThoiDiem), 0) AS TongDoanhThuDV
FROM SU_DUNG_DV sd
JOIN CHI_NHANH cn ON cn.MaCN = sd.MaCN
JOIN DICH_VU dv ON dv.MaDV = sd.MaDV
GROUP BY cn.MaCN, cn.TenCN, dv.MaDV, dv.TenDV, dv.LoaiDV;

-- 1.5. Tong hop phan quyen RBAC va pham vi chi nhanh cua tai khoan
CREATE OR REPLACE VIEW vw_phan_quyen_tai_khoan AS
SELECT
    tk.MaTK,
    tk.TenDangNhap,
    tk.TrangThai AS TrangThaiTaiKhoan,
    tk.MaNV,
    tk.MaKH,
    vt.MaCode AS MaVaiTro,
    vt.TenVaiTro,
    q.MaCode AS MaQuyen,
    q.NhomQuyen,
    pc.MaCN AS MaChiNhanhDuocGiao,
    pc.VaiTroTaiCN,
    pc.NgayBatDau,
    pc.NgayKetThuc
FROM TAI_KHOAN tk
JOIN TAI_KHOAN_VAI_TRO tvt ON tvt.MaTK = tk.MaTK
JOIN VAI_TRO vt ON vt.MaVaiTro = tvt.MaVaiTro
JOIN VAI_TRO_QUYEN vtq ON vtq.MaVaiTro = vt.MaVaiTro
JOIN QUYEN q ON q.MaQuyen = vtq.MaQuyen
LEFT JOIN PHAN_CONG_CHI_NHANH pc
    ON pc.MaTK = tk.MaTK
   AND (pc.NgayKetThuc IS NULL OR pc.NgayKetThuc >= CURRENT_DATE());

-- =============================================================================
-- PHAN 2: FUNCTION VA STORED PROCEDURE NGHIEP VU
-- =============================================================================

DELIMITER $$

-- 2.1. Tra gia phong 1 dem theo loai phong va ngay duong lich (uu tien le co dinh MM-DD,
--      sau do den gia mua MM-DD; cac moc le am lich dang chu can bang quy doi rieng).
DROP FUNCTION IF EXISTS fn_gia_phong_theo_ngay$$
CREATE FUNCTION fn_gia_phong_theo_ngay(
    p_MaLP VARCHAR(10),
    p_Ngay DATE
) RETURNS DECIMAL(14,2)
READS SQL DATA
BEGIN
    DECLARE v_mmdd CHAR(5);
    DECLARE v_Gia DECIMAL(14,2) DEFAULT NULL;

    SET v_mmdd = DATE_FORMAT(p_Ngay, '%m-%d');

    -- Uu tien ngay le co dinh dinh dang MM-DD, sau do den gia theo mua (ke ca mua vat qua nam 12-01..02-28)
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

    -- Truong hop dac biet ngay 29/02 nam nhuan fallback ve gia mua Dong M01
    IF v_Gia IS NULL AND v_mmdd = '02-29' THEN
        SELECT bg.GiaPhong INTO v_Gia
        FROM BANG_GIA bg
        WHERE bg.MaLP = p_MaLP AND bg.MaMua = 'M01' AND bg.MaSuKienLe = 'Không'
        LIMIT 1;
    END IF;

    RETURN v_Gia;
END$$

-- 2.2. Tim phong kha dung theo chi nhanh, khoang ngay va suc chua toi thieu
DROP PROCEDURE IF EXISTS sp_tim_phong_trong$$
CREATE PROCEDURE sp_tim_phong_trong(
    IN p_MaCN INT,
    IN p_NgayCheckIn DATE,
    IN p_NgayCheckOut DATE,
    IN p_SucChua INT
)
BEGIN
    IF p_NgayCheckOut <= p_NgayCheckIn THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'NgayCheckOut phai lon hon NgayCheckIn';
    END IF;

    SELECT
        p.MaPhong,
        p.SoPhong,
        p.Tang,
        p.TrangThai AS TrangThaiHienTai,
        lp.MaLP,
        lp.TenLP,
        lp.SucChua,
        DATEDIFF(p_NgayCheckOut, p_NgayCheckIn) AS SoDem,
        fn_gia_phong_theo_ngay(lp.MaLP, p_NgayCheckIn) AS DonGiaDemDau,
        fn_gia_phong_theo_ngay(lp.MaLP, p_NgayCheckIn) * DATEDIFF(p_NgayCheckOut, p_NgayCheckIn) AS GiaTamTinh
    FROM PHONG p
    JOIN LOAI_PHONG lp ON lp.MaLP = p.MaLP
    WHERE p.MaCN = p_MaCN
      AND p.TrangThai <> 'Bảo trì'
      AND lp.SucChua >= p_SucChua
      AND NOT EXISTS (
          SELECT 1
          FROM CT_DAT_PHONG c
          JOIN DAT_PHONG d ON d.MaDP = c.MaDP
          WHERE c.MaPhong = p.MaPhong
            AND d.TrangThai IN ('Đã xác nhận', 'Đang lưu trú')
            AND p_NgayCheckIn < c.NgayCheckOut
            AND p_NgayCheckOut > c.NgayCheckIn
      )
    ORDER BY lp.SucChua, p.Tang, p.SoPhong;
END$$

-- 2.3. Tao dat phong 1 phong kem hoa don tam tinh trong TRANSACTION + FOR UPDATE
DROP PROCEDURE IF EXISTS sp_tao_dat_phong$$
CREATE PROCEDURE sp_tao_dat_phong(
    IN p_MaKH INT,
    IN p_MaPhong INT,
    IN p_NgayCheckIn DATE,
    IN p_NgayCheckOut DATE,
    IN p_GhiChu TEXT,
    IN p_MaTK BIGINT,
    OUT p_MaDP INT,
    OUT p_MaHD INT
)
BEGIN
    DECLARE v_TrangThaiPhong VARCHAR(30);
    DECLARE v_MaLP VARCHAR(10);
    DECLARE v_SoPhong VARCHAR(20);
    DECLARE v_SoDem INT;
    DECLARE v_DonGiaDem DECIMAL(14,2);
    DECLARE v_GiaThoaThuan DECIMAL(14,2);
    DECLARE v_MaCTDP INT;
    DECLARE v_MaCTHD INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_NgayCheckOut <= p_NgayCheckIn THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'NgayCheckOut phai sau NgayCheckIn';
    END IF;

    SET v_SoDem = DATEDIFF(p_NgayCheckOut, p_NgayCheckIn);

    START TRANSACTION;

    -- Khoa dong phong de chong dat dong thoi (race condition)
    SELECT p.TrangThai, p.MaLP, p.SoPhong
    INTO v_TrangThaiPhong, v_MaLP, v_SoPhong
    FROM PHONG p
    WHERE p.MaPhong = p_MaPhong
    FOR UPDATE;

    IF v_TrangThaiPhong IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Phong khong ton tai';
    END IF;

    IF v_TrangThaiPhong = 'Bảo trì' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Phong dang bao tri, khong the dat';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM CT_DAT_PHONG c
        JOIN DAT_PHONG d ON d.MaDP = c.MaDP
        WHERE c.MaPhong = p_MaPhong
          AND d.TrangThai IN ('Đã xác nhận', 'Đang lưu trú')
          AND p_NgayCheckIn < c.NgayCheckOut
          AND p_NgayCheckOut > c.NgayCheckIn
    ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Phong da co lich dat trung khoang ngay';
    END IF;

    SET v_DonGiaDem = fn_gia_phong_theo_ngay(v_MaLP, p_NgayCheckIn);
    IF v_DonGiaDem IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong tim thay don gia phu hop cho loai phong';
    END IF;
    SET v_GiaThoaThuan = v_DonGiaDem * v_SoDem;

    -- Sinh khoa chinh tuan tu cho cac bang nghiep vu (khong dung AUTO_INCREMENT theo schema goc)
    SELECT COALESCE(MAX(MaDP), 0) + 1 INTO p_MaDP FROM DAT_PHONG FOR UPDATE;
    SELECT COALESCE(MAX(MaCTDP), 0) + 1 INTO v_MaCTDP FROM CT_DAT_PHONG FOR UPDATE;
    SELECT COALESCE(MAX(MaHD), 0) + 1 INTO p_MaHD FROM HOA_DON FOR UPDATE;
    SELECT COALESCE(MAX(MaCTHD), 0) + 1 INTO v_MaCTHD FROM CT_HOA_DON FOR UPDATE;

    INSERT INTO DAT_PHONG (MaDP, MaKH, NgayDat, TrangThai, GhiChu)
    VALUES (p_MaDP, p_MaKH, NOW(), 'Chờ xác nhận', p_GhiChu);

    INSERT INTO CT_DAT_PHONG (MaCTDP, MaDP, MaPhong, NgayCheckIn, NgayCheckOut, GiaThoaThuan)
    VALUES (v_MaCTDP, p_MaDP, p_MaPhong, p_NgayCheckIn, p_NgayCheckOut, v_GiaThoaThuan);

    INSERT INTO HOA_DON (MaHD, MaDP, NgayLap, TongTien, TienCoc, TrangThai)
    VALUES (p_MaHD, p_MaDP, NOW(), 0, ROUND(v_GiaThoaThuan * 0.30, 2), 'Chưa thanh toán');

    -- Trigger trg_cthd_total_insert se tu dong cap nhat HOA_DON.TongTien
    INSERT INTO CT_HOA_DON (MaCTHD, MaHD, LoaiKhoanThu, MoTa, SoLuong, DonGia)
    VALUES (
        v_MaCTHD,
        p_MaHD,
        'Tiền phòng',
        CONCAT('Tiền phòng ', v_SoPhong, ' (', v_SoDem, ' đêm)'),
        v_SoDem,
        v_DonGiaDem
    );

    IF p_MaTK IS NOT NULL THEN
        INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriMoi, LyDo)
        VALUES (
            p_MaTK,
            'TAO_DAT_PHONG',
            'DAT_PHONG',
            CAST(p_MaDP AS CHAR),
            JSON_OBJECT('MaKH', p_MaKH, 'MaPhong', p_MaPhong, 'GiaThoaThuan', v_GiaThoaThuan),
            'Tao dat phong moi'
        );
    END IF;

    COMMIT;
END$$

-- 2.4. Xac nhan dat phong (kich hoat trigger kiem tra trung lich va ghi nhat ky)
DROP PROCEDURE IF EXISTS sp_xac_nhan_dat_phong$$
CREATE PROCEDURE sp_xac_nhan_dat_phong(
    IN p_MaDP INT,
    IN p_MaTK BIGINT
)
BEGIN
    DECLARE v_TrangThaiCu VARCHAR(40);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT TrangThai INTO v_TrangThaiCu
    FROM DAT_PHONG
    WHERE MaDP = p_MaDP
    FOR UPDATE;

    IF v_TrangThaiCu IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong tim thay ma dat phong';
    END IF;

    IF v_TrangThaiCu = 'Đã hủy' OR v_TrangThaiCu = 'Đã trả phòng' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Trang thai dat phong khong hop le de xac nhan';
    END IF;

    UPDATE DAT_PHONG
    SET TrangThai = 'Đã xác nhận'
    WHERE MaDP = p_MaDP;

    IF p_MaTK IS NOT NULL THEN
        INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriCu, GiaTriMoi, LyDo)
        VALUES (
            p_MaTK,
            'XAC_NHAN_DAT_PHONG',
            'DAT_PHONG',
            CAST(p_MaDP AS CHAR),
            JSON_OBJECT('TrangThai', v_TrangThaiCu),
            JSON_OBJECT('TrangThai', 'Đã xác nhận'),
            'Le tan/Quan ly xac nhan dat phong'
        );
    END IF;

    COMMIT;
END$$

-- 2.5. Ghi nhan giao dich thanh toan va tu dong cap nhat trang thai hoa don
DROP PROCEDURE IF EXISTS sp_ghi_nhan_thanh_toan$$
CREATE PROCEDURE sp_ghi_nhan_thanh_toan(
    IN p_MaHD INT,
    IN p_CongThanhToan VARCHAR(40),
    IN p_MaGiaoDichCong VARCHAR(120),
    IN p_SoTien DECIMAL(16,2),
    IN p_NoiDung VARCHAR(300),
    IN p_MaTK BIGINT
)
BEGIN
    DECLARE v_TongTien DECIMAL(16,2);
    DECLARE v_TrangThaiCu VARCHAR(40);
    DECLARE v_TongDaThu DECIMAL(16,2);
    DECLARE v_MaGiaoDich INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_SoTien <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'So tien thanh toan phai lon hon 0';
    END IF;

    START TRANSACTION;

    SELECT TongTien, TrangThai INTO v_TongTien, v_TrangThaiCu
    FROM HOA_DON
    WHERE MaHD = p_MaHD
    FOR UPDATE;

    IF v_TongTien IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Hoa don khong ton tai';
    END IF;

    SELECT COALESCE(MAX(MaGiaoDich), 0) + 1 INTO v_MaGiaoDich
    FROM GIAO_DICH_THANH_TOAN
    FOR UPDATE;

    INSERT INTO GIAO_DICH_THANH_TOAN (
        MaGiaoDich, MaHD, CongThanhToan, MaGiaoDichCong, SoTien, ThoiGianGD, TrangThai, NoiDungChuyenKhoan
    ) VALUES (
        v_MaGiaoDich, p_MaHD, p_CongThanhToan, p_MaGiaoDichCong, p_SoTien, NOW(), 'Thành công', p_NoiDung
    );

    SELECT COALESCE(SUM(SoTien), 0) INTO v_TongDaThu
    FROM GIAO_DICH_THANH_TOAN
    WHERE MaHD = p_MaHD AND TrangThai = 'Thành công';

    IF v_TongDaThu >= v_TongTien THEN
        UPDATE HOA_DON SET TrangThai = 'Đã thanh toán' WHERE MaHD = p_MaHD;
    ELSE
        UPDATE HOA_DON SET TrangThai = 'Thanh toán một phần' WHERE MaHD = p_MaHD;
    END IF;

    IF p_MaTK IS NOT NULL THEN
        INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriCu, GiaTriMoi, LyDo)
        VALUES (
            p_MaTK,
            'GHI_NHAN_THANH_TOAN',
            'HOA_DON',
            CAST(p_MaHD AS CHAR),
            JSON_OBJECT('TrangThai', v_TrangThaiCu),
            JSON_OBJECT('MaGiaoDich', v_MaGiaoDich, 'SoTien', p_SoTien, 'TongDaThu', v_TongDaThu),
            'Ghi nhan thanh toan hoa don'
        );
    END IF;

    COMMIT;
END$$

DELIMITER ;
