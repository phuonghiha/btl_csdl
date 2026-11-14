USE quan_ly_khach_san;
DELIMITER $$

-- Khong cho phong co hai dat phong da xac nhan trung khoang luu tru.
CREATE TRIGGER trg_ctdp_no_overlap_insert
BEFORE INSERT ON CT_DAT_PHONG FOR EACH ROW
BEGIN
  IF EXISTS (
    SELECT 1 FROM CT_DAT_PHONG c
    JOIN DAT_PHONG d ON d.MaDP=c.MaDP
    WHERE c.MaPhong=NEW.MaPhong AND d.TrangThai='Đã xác nhận'
      AND NEW.NgayCheckIn<c.NgayCheckOut AND NEW.NgayCheckOut>c.NgayCheckIn
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Phong da co dat phong da xac nhan trong khoang ngay nay';
  END IF;
END$$

CREATE TRIGGER trg_ctdp_no_overlap_update
BEFORE UPDATE ON CT_DAT_PHONG FOR EACH ROW
BEGIN
  IF EXISTS (
    SELECT 1 FROM CT_DAT_PHONG c
    JOIN DAT_PHONG d ON d.MaDP=c.MaDP
    WHERE c.MaPhong=NEW.MaPhong AND c.MaCTDP<>OLD.MaCTDP
      AND d.TrangThai='Đã xác nhận'
      AND NEW.NgayCheckIn<c.NgayCheckOut AND NEW.NgayCheckOut>c.NgayCheckIn
  ) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Phong da co dat phong da xac nhan trong khoang ngay nay';
  END IF;
END$$

-- Kiem tra trung phong khi chuyen phieu dat sang da xac nhan.
CREATE TRIGGER trg_datphong_confirm_no_overlap
BEFORE UPDATE ON DAT_PHONG FOR EACH ROW
BEGIN
  IF NEW.TrangThai='Đã xác nhận' AND OLD.TrangThai<>'Đã xác nhận' THEN
    IF EXISTS (
      SELECT 1 FROM CT_DAT_PHONG a
      JOIN CT_DAT_PHONG b ON b.MaPhong=a.MaPhong AND b.MaCTDP<>a.MaCTDP
      JOIN DAT_PHONG d ON d.MaDP=b.MaDP
      WHERE a.MaDP=NEW.MaDP AND d.TrangThai='Đã xác nhận'
        AND a.NgayCheckIn<b.NgayCheckOut AND a.NgayCheckOut>b.NgayCheckIn
    ) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Khong the xac nhan: co phong bi trung lich';
    END IF;
  END IF;
END$$

-- Dong bo tong hoa don voi cac dong chi tiet. Chay trigger sau khi import CSV.
CREATE TRIGGER trg_cthd_total_insert AFTER INSERT ON CT_HOA_DON FOR EACH ROW
BEGIN
  UPDATE HOA_DON SET TongTien=(SELECT COALESCE(SUM(SoLuong*DonGia),0) FROM CT_HOA_DON WHERE MaHD=NEW.MaHD)
  WHERE MaHD=NEW.MaHD;
END$$
CREATE TRIGGER trg_cthd_total_update AFTER UPDATE ON CT_HOA_DON FOR EACH ROW
BEGIN
  UPDATE HOA_DON SET TongTien=(SELECT COALESCE(SUM(SoLuong*DonGia),0) FROM CT_HOA_DON WHERE MaHD=NEW.MaHD)
  WHERE MaHD=NEW.MaHD;
  IF OLD.MaHD<>NEW.MaHD THEN
    UPDATE HOA_DON SET TongTien=(SELECT COALESCE(SUM(SoLuong*DonGia),0) FROM CT_HOA_DON WHERE MaHD=OLD.MaHD)
    WHERE MaHD=OLD.MaHD;
  END IF;
END$$
CREATE TRIGGER trg_cthd_total_delete AFTER DELETE ON CT_HOA_DON FOR EACH ROW
BEGIN
  UPDATE HOA_DON SET TongTien=(SELECT COALESCE(SUM(SoLuong*DonGia),0) FROM CT_HOA_DON WHERE MaHD=OLD.MaHD)
  WHERE MaHD=OLD.MaHD;
END$$

DELIMITER ;
