-- =============================================================================
-- 11_operations_procedures.sql
-- Cac STORED PROCEDURE van hanh nghiep vu con lai:
--   1. sp_checkin_dat_phong
--   2. sp_checkout_dat_phong
--   3. sp_huy_dat_phong
--   4. sp_ghi_nhan_su_dung_dv
--   5. sp_ap_ma_giam_gia
--   6. sp_quet_ve_dien_tu
-- Yeu cau: da chay 01..10
-- =============================================================================

USE quan_ly_khach_san;
SET NAMES utf8mb4;

DELIMITER $$

-- 1. Check-in dat phong: chuyen don sang 'Đang lưu trú' va cac phong thuoc don sang 'Đang sử dụng'
DROP PROCEDURE IF EXISTS sp_checkin_dat_phong$$
CREATE PROCEDURE sp_checkin_dat_phong(
    IN p_MaDP INT,
    IN p_MaTK BIGINT
)
BEGIN
    DECLARE v_TrangThaiCu VARCHAR(40);
    DECLARE v_PhongBaoTri INT DEFAULT 0;

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
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong tim thay don dat phong';
    END IF;

    IF v_TrangThaiCu <> 'Đã xác nhận' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Chi duoc check-in don o trang thai Da xac nhan';
    END IF;

    SELECT COUNT(*) INTO v_PhongBaoTri
    FROM CT_DAT_PHONG c
    JOIN PHONG p ON p.MaPhong = c.MaPhong
    WHERE c.MaDP = p_MaDP AND p.TrangThai = 'Bảo trì';

    IF v_PhongBaoTri > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Co phong thuoc don dang o trang thai Bao tri';
    END IF;

    UPDATE DAT_PHONG
    SET TrangThai = 'Đang lưu trú'
    WHERE MaDP = p_MaDP;

    UPDATE PHONG p
    JOIN CT_DAT_PHONG c ON c.MaPhong = p.MaPhong
    SET p.TrangThai = 'Đang sử dụng'
    WHERE c.MaDP = p_MaDP;

    IF p_MaTK IS NOT NULL THEN
        INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriCu, GiaTriMoi, LyDo)
        VALUES (
            p_MaTK,
            'CHECK_IN',
            'DAT_PHONG',
            CAST(p_MaDP AS CHAR),
            JSON_OBJECT('TrangThai', v_TrangThaiCu),
            JSON_OBJECT('TrangThai', 'Đang lưu trú'),
            'Khach nhan phong (check-in)'
        );
    END IF;

    COMMIT;
END$$

-- 2. Check-out dat phong: chuyen don sang 'Đã trả phòng' va phong ve 'Trống'
DROP PROCEDURE IF EXISTS sp_checkout_dat_phong$$
CREATE PROCEDURE sp_checkout_dat_phong(
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
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong tim thay don dat phong';
    END IF;

    IF v_TrangThaiCu NOT IN ('Đang lưu trú', 'Đã xác nhận') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Trang thai don khong hop le de check-out';
    END IF;

    UPDATE DAT_PHONG
    SET TrangThai = 'Đã trả phòng'
    WHERE MaDP = p_MaDP;

    UPDATE PHONG p
    JOIN CT_DAT_PHONG c ON c.MaPhong = p.MaPhong
    SET p.TrangThai = 'Trống'
    WHERE c.MaDP = p_MaDP AND p.TrangThai = 'Đang sử dụng';

    IF p_MaTK IS NOT NULL THEN
        INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriCu, GiaTriMoi, LyDo)
        VALUES (
            p_MaTK,
            'CHECK_OUT',
            'DAT_PHONG',
            CAST(p_MaDP AS CHAR),
            JSON_OBJECT('TrangThai', v_TrangThaiCu),
            JSON_OBJECT('TrangThai', 'Đã trả phòng'),
            'Khach tra phong (check-out)'
        );
    END IF;

    COMMIT;
END$$

-- 3. Huy dat phong: chi huy khi dang 'Chờ xác nhận' hoac 'Đã xác nhận', bat buoc ghi ly do
DROP PROCEDURE IF EXISTS sp_huy_dat_phong$$
CREATE PROCEDURE sp_huy_dat_phong(
    IN p_MaDP INT,
    IN p_LyDo VARCHAR(500),
    IN p_MaTK BIGINT
)
BEGIN
    DECLARE v_TrangThaiCu VARCHAR(40);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_LyDo IS NULL OR TRIM(p_LyDo) = '' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Can nhap ly do huy dat phong';
    END IF;

    START TRANSACTION;

    SELECT TrangThai INTO v_TrangThaiCu
    FROM DAT_PHONG
    WHERE MaDP = p_MaDP
    FOR UPDATE;

    IF v_TrangThaiCu IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong tim thay don dat phong';
    END IF;

    IF v_TrangThaiCu NOT IN ('Chờ xác nhận', 'Đã xác nhận') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong the huy don da check-in, da tra phong hoac da huy';
    END IF;

    UPDATE DAT_PHONG
    SET TrangThai = 'Đã hủy'
    WHERE MaDP = p_MaDP;

    IF p_MaTK IS NOT NULL THEN
        INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriCu, GiaTriMoi, LyDo)
        VALUES (
            p_MaTK,
            'HUY_DAT_PHONG',
            'DAT_PHONG',
            CAST(p_MaDP AS CHAR),
            JSON_OBJECT('TrangThai', v_TrangThaiCu),
            JSON_OBJECT('TrangThai', 'Đã hủy'),
            p_LyDo
        );
    END IF;

    COMMIT;
END$$

-- 4. Ghi nhan su dung dich vu: lay don gia hien hanh tai chi nhanh (snapshot),
--    them vao SU_DUNG_DV va CT_HOA_DON (trigger tu dong cong HOA_DON.TongTien)
DROP PROCEDURE IF EXISTS sp_ghi_nhan_su_dung_dv$$
CREATE PROCEDURE sp_ghi_nhan_su_dung_dv(
    IN p_MaDP INT,
    IN p_MaCN INT,
    IN p_MaDV INT,
    IN p_SoLuong INT,
    IN p_MaTK BIGINT,
    OUT p_MaSD INT
)
BEGIN
    DECLARE v_TrangThaiDP VARCHAR(40);
    DECLARE v_DonGia DECIMAL(14,2);
    DECLARE v_TrangThaiDV VARCHAR(30);
    DECLARE v_TenDV VARCHAR(180);
    DECLARE v_MaHD INT;
    DECLARE v_MaCTHD INT;
    DECLARE v_DungChiNhanh INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_SoLuong <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'So luong dich vu phai lon hon 0';
    END IF;

    START TRANSACTION;

    SELECT TrangThai INTO v_TrangThaiDP
    FROM DAT_PHONG
    WHERE MaDP = p_MaDP
    FOR UPDATE;

    IF v_TrangThaiDP IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong tim thay don dat phong';
    END IF;

    IF v_TrangThaiDP NOT IN ('Đã xác nhận', 'Đang lưu trú') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Chi ghi nhan dich vu cho don Da xac nhan hoac Dang luu tru';
    END IF;

    SELECT COUNT(*) INTO v_DungChiNhanh
    FROM CT_DAT_PHONG c
    JOIN PHONG p ON p.MaPhong = c.MaPhong
    WHERE c.MaDP = p_MaDP AND p.MaCN = p_MaCN;

    IF v_DungChiNhanh = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Don dat phong khong co phong tai chi nhanh nay';
    END IF;

    SELECT dcn.DonGia, dcn.TrangThai, dv.TenDV
    INTO v_DonGia, v_TrangThaiDV, v_TenDV
    FROM DV_CHI_NHANH dcn
    JOIN DICH_VU dv ON dv.MaDV = dcn.MaDV
    WHERE dcn.MaCN = p_MaCN AND dcn.MaDV = p_MaDV;

    IF v_DonGia IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Chi nhanh khong cung cap dich vu nay';
    END IF;

    IF v_TrangThaiDV <> 'Đang cung cấp' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Dich vu hien dang tam ngung tai chi nhanh';
    END IF;

    SELECT MaHD INTO v_MaHD
    FROM HOA_DON
    WHERE MaDP = p_MaDP
    FOR UPDATE;

    IF v_MaHD IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Chua co hoa don cho don dat phong nay';
    END IF;

    SELECT COALESCE(MAX(MaSD), 0) + 1 INTO p_MaSD FROM SU_DUNG_DV FOR UPDATE;
    SELECT COALESCE(MAX(MaCTHD), 0) + 1 INTO v_MaCTHD FROM CT_HOA_DON FOR UPDATE;

    INSERT INTO SU_DUNG_DV (MaSD, MaDP, MaCN, MaDV, ThoiGianSD, SoLuong, DonGiaTaiThoiDiem)
    VALUES (p_MaSD, p_MaDP, p_MaCN, p_MaDV, NOW(), p_SoLuong, v_DonGia);

    INSERT INTO CT_HOA_DON (MaCTHD, MaHD, LoaiKhoanThu, MoTa, SoLuong, DonGia)
    VALUES (v_MaCTHD, v_MaHD, 'Dịch vụ', CONCAT(v_TenDV, ' (x', p_SoLuong, ')'), p_SoLuong, v_DonGia);

    IF p_MaTK IS NOT NULL THEN
        INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriMoi, LyDo)
        VALUES (
            p_MaTK,
            'GHI_NHAN_DICH_VU',
            'SU_DUNG_DV',
            CAST(p_MaSD AS CHAR),
            JSON_OBJECT('MaDP', p_MaDP, 'MaDV', p_MaDV, 'SoLuong', p_SoLuong, 'DonGia', v_DonGia),
            'Ghi nhan su dung dich vu va cong vao hoa don'
        );
    END IF;

    COMMIT;
END$$

-- 5. Ap ma giam gia cho hoa don: kiem tra hieu luc, so luot con lai, don toi thieu;
--    ghi nhan khoan giam gia nhu mot giao dich 'VOUCHER' de giu nguyen tinh toan ven
--    TongTien = SUM(CT_HOA_DON) va chong ap trung nho UNIQUE(CongThanhToan, MaGiaoDichCong).
DROP PROCEDURE IF EXISTS sp_ap_ma_giam_gia$$
CREATE PROCEDURE sp_ap_ma_giam_gia(
    IN p_MaHD INT,
    IN p_Code VARCHAR(60),
    IN p_MaTK BIGINT,
    OUT p_SoTienGiam DECIMAL(16,2)
)
BEGIN
    DECLARE v_TongTien DECIMAL(16,2);
    DECLARE v_TongDaThu DECIMAL(16,2);
    DECLARE v_ConNo DECIMAL(16,2);
    DECLARE v_MaVoucher INT;
    DECLARE v_LoaiGiam VARCHAR(50);
    DECLARE v_GiaTriGiam DECIMAL(14,2);
    DECLARE v_DonToiThieu DECIMAL(14,2);
    DECLARE v_GiamToiDa DECIMAL(14,2);
    DECLARE v_PhatHanh INT;
    DECLARE v_DaDung INT;
    DECLARE v_NgayBD DATE;
    DECLARE v_NgayKT DATE;
    DECLARE v_TrangThaiVC VARCHAR(30);
    DECLARE v_MaGiaoDich INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT TongTien INTO v_TongTien
    FROM HOA_DON
    WHERE MaHD = p_MaHD
    FOR UPDATE;

    IF v_TongTien IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Hoa don khong ton tai';
    END IF;

    SELECT MaVoucher, LoaiGiam, GiaTriGiam, DonHangToiThieu, GiamToiDa,
           SoLuongPhatHanh, SoLuongDaDung, NgayBatDau, NgayKetThuc, TrangThai
    INTO v_MaVoucher, v_LoaiGiam, v_GiaTriGiam, v_DonToiThieu, v_GiamToiDa,
         v_PhatHanh, v_DaDung, v_NgayBD, v_NgayKT, v_TrangThaiVC
    FROM MA_GIAM_GIA
    WHERE Code = p_Code
    FOR UPDATE;

    IF v_MaVoucher IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ma giam gia khong ton tai';
    END IF;

    IF v_TrangThaiVC <> 'Hiệu lực' OR CURRENT_DATE() < v_NgayBD OR CURRENT_DATE() > v_NgayKT THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ma giam gia het hieu luc hoac ngoai thoi gian ap dung';
    END IF;

    IF v_DaDung >= v_PhatHanh THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ma giam gia da het luot su dung';
    END IF;

    IF v_TongTien < v_DonToiThieu THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Hoa don chua dat gia tri don hang toi thieu';
    END IF;

    IF v_LoaiGiam = 'Phần trăm' THEN
        SET p_SoTienGiam = ROUND(v_TongTien * v_GiaTriGiam / 100.0, 2);
        IF v_GiamToiDa IS NOT NULL AND p_SoTienGiam > v_GiamToiDa THEN
            SET p_SoTienGiam = v_GiamToiDa;
        END IF;
    ELSE
        SET p_SoTienGiam = v_GiaTriGiam;
    END IF;

    SELECT COALESCE(SUM(SoTien), 0) INTO v_TongDaThu
    FROM GIAO_DICH_THANH_TOAN
    WHERE MaHD = p_MaHD AND TrangThai = 'Thành công';

    SET v_ConNo = v_TongTien - v_TongDaThu;
    IF v_ConNo <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Hoa don da duoc thanh toan du';
    END IF;

    IF p_SoTienGiam > v_ConNo THEN
        SET p_SoTienGiam = v_ConNo;
    END IF;

    SELECT COALESCE(MAX(MaGiaoDich), 0) + 1 INTO v_MaGiaoDich
    FROM GIAO_DICH_THANH_TOAN
    FOR UPDATE;

    INSERT INTO GIAO_DICH_THANH_TOAN (
        MaGiaoDich, MaHD, CongThanhToan, MaGiaoDichCong, SoTien, ThoiGianGD, TrangThai, NoiDungChuyenKhoan
    ) VALUES (
        v_MaGiaoDich,
        p_MaHD,
        'VOUCHER',
        CONCAT('VOUCHER-', p_Code, '-HD', p_MaHD),
        p_SoTienGiam,
        NOW(),
        'Thành công',
        CONCAT('Ap ma giam gia ', p_Code)
    );

    UPDATE MA_GIAM_GIA
    SET SoLuongDaDung = SoLuongDaDung + 1
    WHERE MaVoucher = v_MaVoucher;

    IF (v_TongDaThu + p_SoTienGiam) >= v_TongTien THEN
        UPDATE HOA_DON SET TrangThai = 'Đã thanh toán' WHERE MaHD = p_MaHD;
    ELSE
        UPDATE HOA_DON SET TrangThai = 'Thanh toán một phần' WHERE MaHD = p_MaHD;
    END IF;

    IF p_MaTK IS NOT NULL THEN
        INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriMoi, LyDo)
        VALUES (
            p_MaTK,
            'AP_MA_GIAM_GIA',
            'HOA_DON',
            CAST(p_MaHD AS CHAR),
            JSON_OBJECT('Code', p_Code, 'SoTienGiam', p_SoTienGiam),
            'Ap ma giam gia cho hoa don'
        );
    END IF;

    COMMIT;
END$$

-- 6. Quet ve dien tu QR tai cong khu vui choi (kiem tra dung chi nhanh, trang thai va ngay su dung)
DROP PROCEDURE IF EXISTS sp_quet_ve_dien_tu$$
CREATE PROCEDURE sp_quet_ve_dien_tu(
    IN p_MaQR VARCHAR(120),
    IN p_MaCN_Quet INT,
    IN p_MaTK BIGINT
)
BEGIN
    DECLARE v_MaVe INT;
    DECLARE v_TrangThai VARCHAR(40);
    DECLARE v_NgaySuDung DATE;
    DECLARE v_MaCN_Khu INT;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT ve.MaVe, ve.TrangThai, ve.NgaySuDung, kv.MaCN
    INTO v_MaVe, v_TrangThai, v_NgaySuDung, v_MaCN_Khu
    FROM VE_DIEN_TU ve
    JOIN LOAI_VE lv ON lv.MaLoaiVe = ve.MaLoaiVe
    JOIN KHU_VUI_CHOI kv ON kv.MaKhu = lv.MaKhu
    WHERE ve.MaQR = p_MaQR
    FOR UPDATE;

    IF v_MaVe IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Khong tim thay ve dien tu voi ma QR nay';
    END IF;

    IF v_MaCN_Khu <> p_MaCN_Quet THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ve khong thuoc khu vui choi cua chi nhanh nay';
    END IF;

    IF v_TrangThai <> 'Chưa sử dụng' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ve da duoc su dung hoac da het han';
    END IF;

    IF CURRENT_DATE() > v_NgaySuDung THEN
        UPDATE VE_DIEN_TU SET TrangThai = 'Hết hạn' WHERE MaVe = v_MaVe;
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Ve da qua ngay su dung va chuyen sang Het han';
    END IF;

    UPDATE VE_DIEN_TU
    SET TrangThai = 'Đã sử dụng',
        ThoiGianQuet = NOW()
    WHERE MaVe = v_MaVe;

    IF p_MaTK IS NOT NULL THEN
        INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriCu, GiaTriMoi, LyDo)
        VALUES (
            p_MaTK,
            'QUET_VE_QR',
            'VE_DIEN_TU',
            CAST(v_MaVe AS CHAR),
            JSON_OBJECT('TrangThai', v_TrangThai),
            JSON_OBJECT('TrangThai', 'Đã sử dụng', 'MaQR', p_MaQR),
            'Soat ve QR tai cong khu vui choi'
        );
    END IF;

    COMMIT;
END$$

DELIMITER ;
