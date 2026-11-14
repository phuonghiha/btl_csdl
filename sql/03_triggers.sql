USE quan_ly_khach_san;
DELIMITER $$

/*
  FILE: 03_triggers.sql

  Cac rang buoc CHECK va FOREIGN KEY duoc khai bao truc tiep trong
  sql/01_schema.sql, khong can tao lai bang trigger:
    - LOAI_PHONG.SucChua > 0.
    - BANG_GIA.GiaPhong > 0.
    - CT_DAT_PHONG.NgayCheckOut > NgayCheckIn.
    - PHONG.MaLP tham chieu LOAI_PHONG.MaLP.
    - BANG_GIA.MaLP tham chieu LOAI_PHONG.MaLP.
    - GOI_COMBO.MaLP tham chieu LOAI_PHONG.MaLP.

  Trigger trong file nay xu ly cac quy tac nghiep vu:
    1. Khong cho dat trung phong trong khoang thoi gian giao nhau.
    2. Booking da xac nhan / hoa don da thanh toan se giu lich phong.
    3. Tien coc toi thieu 30% tong GiaThoaThuan cua cac phong trong booking.
    4. Tu dong cap nhat TongTien hoa don theo cac dong CT_HOA_DON.

  Quy uoc tinh tien coc:
    Tong gia tri phong dat = SUM(CT_DAT_PHONG.GiaThoaThuan) theo MaDP.
    TienCoc >= 30% * Tong gia tri phong dat.
  Tien dich vu va cac khoan thu khac khong tinh vao co so 30%.
*/

-- =========================================================
-- 1. KIEM TRA TRUNG LICH KHI THEM CHI TIET DAT PHONG
-- =========================================================
DROP TRIGGER IF EXISTS trg_ctdp_no_overlap_insert$$
CREATE TRIGGER trg_ctdp_no_overlap_insert
BEFORE INSERT ON CT_DAT_PHONG
FOR EACH ROW
BEGIN
  IF EXISTS (
    SELECT 1
    FROM CT_DAT_PHONG c
    JOIN DAT_PHONG d ON d.MaDP = c.MaDP
    LEFT JOIN HOA_DON h ON h.MaDP = d.MaDP
    WHERE c.MaPhong = NEW.MaPhong
      AND d.MaDP <> NEW.MaDP
      AND (
        d.TrangThai IN ('Đã xác nhận', 'Đã trả phòng')
        OR h.TrangThai = 'Đã thanh toán'
      )
      AND NEW.NgayCheckIn < c.NgayCheckOut
      AND NEW.NgayCheckOut > c.NgayCheckIn
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Phong da duoc dat/xac nhan hoac thanh toan trong khoang thoi gian nay';
  END IF;
END$$

-- =========================================================
-- 2. KIEM TRA TRUNG LICH KHI SUA CHI TIET DAT PHONG
-- =========================================================
DROP TRIGGER IF EXISTS trg_ctdp_no_overlap_update$$
CREATE TRIGGER trg_ctdp_no_overlap_update
BEFORE UPDATE ON CT_DAT_PHONG
FOR EACH ROW
BEGIN
  IF EXISTS (
    SELECT 1
    FROM CT_DAT_PHONG c
    JOIN DAT_PHONG d ON d.MaDP = c.MaDP
    LEFT JOIN HOA_DON h ON h.MaDP = d.MaDP
    WHERE c.MaPhong = NEW.MaPhong
      AND c.MaCTDP <> OLD.MaCTDP
      AND d.MaDP <> NEW.MaDP
      AND (
        d.TrangThai IN ('Đã xác nhận', 'Đã trả phòng')
        OR h.TrangThai = 'Đã thanh toán'
      )
      AND NEW.NgayCheckIn < c.NgayCheckOut
      AND NEW.NgayCheckOut > c.NgayCheckIn
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Khong the cap nhat: phong da duoc dat/xac nhan hoac thanh toan trong khoang thoi gian nay';
  END IF;
END$$

-- =========================================================
-- 3. KIEM TRA TRUNG LICH KHI XAC NHAN PHIEU DAT PHONG
--    Dong thoi bat buoc co tien coc >= 30% gia tri phong dat.
-- =========================================================
DROP TRIGGER IF EXISTS trg_datphong_confirm_no_overlap$$
CREATE TRIGGER trg_datphong_confirm_no_overlap
BEFORE UPDATE ON DAT_PHONG
FOR EACH ROW
BEGIN
  DECLARE v_tong_gia_phong DECIMAL(16,2) DEFAULT 0;
  DECLARE v_tien_coc DECIMAL(16,2) DEFAULT NULL;

  IF NEW.TrangThai = 'Đã xác nhận'
     AND OLD.TrangThai <> 'Đã xác nhận' THEN

    -- Booking phai co it nhat mot phong.
    SELECT COALESCE(SUM(GiaThoaThuan), 0)
      INTO v_tong_gia_phong
    FROM CT_DAT_PHONG
    WHERE MaDP = NEW.MaDP;

    IF v_tong_gia_phong <= 0 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Khong the xac nhan: phieu dat phong chua co chi tiet phong hop le';
    END IF;

    -- Booking phai co hoa don va tien coc dat toi thieu 30%.
    SELECT MAX(TienCoc)
      INTO v_tien_coc
    FROM HOA_DON
    WHERE MaDP = NEW.MaDP;

    IF v_tien_coc IS NULL OR v_tien_coc < v_tong_gia_phong * 0.30 THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Khong the xac nhan: tien coc phai dat toi thieu 30% tong gia tri phong dat';
    END IF;

    -- Khong duoc xac nhan neu co booking khac giu cung phong va bi overlap.
    IF EXISTS (
      SELECT 1
      FROM CT_DAT_PHONG a
      JOIN CT_DAT_PHONG b
        ON b.MaPhong = a.MaPhong
       AND b.MaCTDP <> a.MaCTDP
      JOIN DAT_PHONG d ON d.MaDP = b.MaDP
      LEFT JOIN HOA_DON h ON h.MaDP = d.MaDP
      WHERE a.MaDP = NEW.MaDP
        AND d.MaDP <> NEW.MaDP
        AND (
          d.TrangThai IN ('Đã xác nhận', 'Đã trả phòng')
          OR h.TrangThai = 'Đã thanh toán'
        )
        AND a.NgayCheckIn < b.NgayCheckOut
        AND a.NgayCheckOut > b.NgayCheckIn
    ) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Khong the xac nhan: co phong bi trung lich voi booking da xac nhan/thanh toan';
    END IF;
  END IF;
END$$

-- =========================================================
-- 4. KIEM TRA TIEN COC KHI TAO HOA DON
-- =========================================================
DROP TRIGGER IF EXISTS trg_hoadon_min_deposit_insert$$
CREATE TRIGGER trg_hoadon_min_deposit_insert
BEFORE INSERT ON HOA_DON
FOR EACH ROW
BEGIN
  DECLARE v_tong_gia_phong DECIMAL(16,2) DEFAULT 0;

  SELECT COALESCE(SUM(GiaThoaThuan), 0)
    INTO v_tong_gia_phong
  FROM CT_DAT_PHONG
  WHERE MaDP = NEW.MaDP;

  IF v_tong_gia_phong > 0
     AND NEW.TienCoc < v_tong_gia_phong * 0.30 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Tien coc phai dat toi thieu 30% tong gia tri phong dat';
  END IF;
END$$

-- =========================================================
-- 5. KIEM TRA TIEN COC KHI CAP NHAT HOA DON
--    Neu chuyen hoa don sang da thanh toan, kiem tra trung lich.
-- =========================================================
DROP TRIGGER IF EXISTS trg_hoadon_min_deposit_update$$
CREATE TRIGGER trg_hoadon_min_deposit_update
BEFORE UPDATE ON HOA_DON
FOR EACH ROW
BEGIN
  DECLARE v_tong_gia_phong DECIMAL(16,2) DEFAULT 0;

  SELECT COALESCE(SUM(GiaThoaThuan), 0)
    INTO v_tong_gia_phong
  FROM CT_DAT_PHONG
  WHERE MaDP = NEW.MaDP;

  IF v_tong_gia_phong > 0
     AND NEW.TienCoc < v_tong_gia_phong * 0.30 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Tien coc phai dat toi thieu 30% tong gia tri phong dat';
  END IF;

  -- Hoa don da thanh toan cung duoc xem la lich dat da duoc giu.
  IF NEW.TrangThai = 'Đã thanh toán'
     AND OLD.TrangThai <> 'Đã thanh toán'
     AND EXISTS (
       SELECT 1
       FROM CT_DAT_PHONG a
       JOIN CT_DAT_PHONG b
         ON b.MaPhong = a.MaPhong
        AND b.MaCTDP <> a.MaCTDP
       JOIN DAT_PHONG d ON d.MaDP = b.MaDP
       LEFT JOIN HOA_DON h ON h.MaDP = d.MaDP
       WHERE a.MaDP = NEW.MaDP
         AND d.MaDP <> NEW.MaDP
         AND (
           d.TrangThai IN ('Đã xác nhận', 'Đã trả phòng')
           OR h.TrangThai = 'Đã thanh toán'
         )
         AND a.NgayCheckIn < b.NgayCheckOut
         AND a.NgayCheckOut > b.NgayCheckIn
     ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Khong the thanh toan: phong bi trung lich voi booking da xac nhan/thanh toan';
  END IF;
END$$

-- =========================================================
-- 6. KHONG CHO SUA CHI TIET PHONG LAM TIEN COC THAP HON 30%
--    Ap dung khi booking da co hoa don.
-- =========================================================
DROP TRIGGER IF EXISTS trg_ctdp_min_deposit_insert$$
CREATE TRIGGER trg_ctdp_min_deposit_insert
BEFORE INSERT ON CT_DAT_PHONG
FOR EACH ROW
BEGIN
  DECLARE v_tong_gia_phong DECIMAL(16,2) DEFAULT 0;
  DECLARE v_tien_coc DECIMAL(16,2) DEFAULT NULL;

  SELECT COALESCE(SUM(GiaThoaThuan), 0) + NEW.GiaThoaThuan
    INTO v_tong_gia_phong
  FROM CT_DAT_PHONG
  WHERE MaDP = NEW.MaDP;

  SELECT MAX(TienCoc)
    INTO v_tien_coc
  FROM HOA_DON
  WHERE MaDP = NEW.MaDP;

  IF v_tien_coc IS NOT NULL
     AND v_tien_coc < v_tong_gia_phong * 0.30 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Khong the them phong: tien coc hien tai thap hon 30% tong gia tri phong dat';
  END IF;
END$$

DROP TRIGGER IF EXISTS trg_ctdp_min_deposit_update$$
CREATE TRIGGER trg_ctdp_min_deposit_update
BEFORE UPDATE ON CT_DAT_PHONG
FOR EACH ROW
BEGIN
  DECLARE v_tong_gia_phong DECIMAL(16,2) DEFAULT 0;
  DECLARE v_tien_coc DECIMAL(16,2) DEFAULT NULL;

  SELECT COALESCE(SUM(GiaThoaThuan), 0) + NEW.GiaThoaThuan
    INTO v_tong_gia_phong
  FROM CT_DAT_PHONG
  WHERE MaDP = NEW.MaDP
    AND MaCTDP <> OLD.MaCTDP;

  SELECT MAX(TienCoc)
    INTO v_tien_coc
  FROM HOA_DON
  WHERE MaDP = NEW.MaDP;

  IF v_tien_coc IS NOT NULL
     AND v_tien_coc < v_tong_gia_phong * 0.30 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Khong the sua phong: tien coc hien tai thap hon 30% tong gia tri phong dat';
  END IF;
END$$

-- =========================================================
-- 7. TU DONG CAP NHAT TONG TIEN HOA DON
--    Giu lai cac trigger cu cua repository.
-- =========================================================
DROP TRIGGER IF EXISTS trg_cthd_total_insert$$
CREATE TRIGGER trg_cthd_total_insert
AFTER INSERT ON CT_HOA_DON
FOR EACH ROW
BEGIN
  UPDATE HOA_DON
  SET TongTien = (
    SELECT COALESCE(SUM(SoLuong * DonGia), 0)
    FROM CT_HOA_DON
    WHERE MaHD = NEW.MaHD
  )
  WHERE MaHD = NEW.MaHD;
END$$

DROP TRIGGER IF EXISTS trg_cthd_total_update$$
CREATE TRIGGER trg_cthd_total_update
AFTER UPDATE ON CT_HOA_DON
FOR EACH ROW
BEGIN
  UPDATE HOA_DON
  SET TongTien = (
    SELECT COALESCE(SUM(SoLuong * DonGia), 0)
    FROM CT_HOA_DON
    WHERE MaHD = NEW.MaHD
  )
  WHERE MaHD = NEW.MaHD;

  IF OLD.MaHD <> NEW.MaHD THEN
    UPDATE HOA_DON
    SET TongTien = (
      SELECT COALESCE(SUM(SoLuong * DonGia), 0)
      FROM CT_HOA_DON
      WHERE MaHD = OLD.MaHD
    )
    WHERE MaHD = OLD.MaHD;
  END IF;
END$$

DROP TRIGGER IF EXISTS trg_cthd_total_delete$$
CREATE TRIGGER trg_cthd_total_delete
AFTER DELETE ON CT_HOA_DON
FOR EACH ROW
BEGIN
  UPDATE HOA_DON
  SET TongTien = (
    SELECT COALESCE(SUM(SoLuong * DonGia), 0)
    FROM CT_HOA_DON
    WHERE MaHD = OLD.MaHD
  )
  WHERE MaHD = OLD.MaHD;
END$$

DELIMITER ;
