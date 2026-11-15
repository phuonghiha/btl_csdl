-- Nhap 21 tep CSV nghiep vu theo dung thu tu phu thuoc trong 05_import_order.md.
-- Chay tu thu muc goc cua repository (hoac thay duong dan tuyet doi toi thu muc data/csv/).
-- Can bat local_infile=1 tren ca MySQL Server va client ket noi.

USE quan_ly_khach_san;
SET NAMES utf8mb4;

-- 1. CHI_NHANH
LOAD DATA LOCAL INFILE 'data/csv/chi_nhanh.csv'
INTO TABLE CHI_NHANH
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaCN, TenCN, DiaChi, @v_SDT, @v_Email)
SET SDT = NULLIF(@v_SDT, ''),
    Email = NULLIF(@v_Email, '');

-- 2. LOAI_PHONG
LOAD DATA LOCAL INFILE 'data/csv/loai_phong.csv'
INTO TABLE LOAI_PHONG
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaLP, TenLP, @v_MoTa, SucChua)
SET MoTa = NULLIF(@v_MoTa, '');

-- 3. KHACH_HANG
LOAD DATA LOCAL INFILE 'data/csv/khach_hang.csv'
INTO TABLE KHACH_HANG
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaKH, HoTen, CCCD, SDT, @v_Email, @v_DiaChi)
SET Email = NULLIF(@v_Email, ''),
    DiaChi = NULLIF(@v_DiaChi, '');

-- 4. DICH_VU
LOAD DATA LOCAL INFILE 'data/csv/dich_vu.csv'
INTO TABLE DICH_VU
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaDV, TenDV, LoaiDV, @v_MoTa)
SET MoTa = NULLIF(@v_MoTa, '');

-- 5. CA_LAM
LOAD DATA LOCAL INFILE 'data/csv/ca_lam.csv'
INTO TABLE CA_LAM
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaCa, TenCa, GioBD, GioKT);

-- 6. KHU_VUI_CHOI
LOAD DATA LOCAL INFILE 'data/csv/khu_vui_choi.csv'
INTO TABLE KHU_VUI_CHOI
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaKhu, MaCN, TenKhu, LoaiKhu, GioMoCua, GioDongCua, @v_MoTa)
SET MoTa = NULLIF(@v_MoTa, '');

-- 7. BANG_GIA
LOAD DATA LOCAL INFILE 'data/csv/bang_gia.csv'
INTO TABLE BANG_GIA
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaBG, MaLP, @v_MaMua, @v_TenMua, @v_MaSuKienLe, NgayBD, NgayKT, GiaPhong, TyLeGiam)
SET MaMua = NULLIF(@v_MaMua, ''),
    TenMua = NULLIF(@v_TenMua, ''),
    MaSuKienLe = NULLIF(@v_MaSuKienLe, '');

-- 8. PHONG
LOAD DATA LOCAL INFILE 'data/csv/phong.csv'
INTO TABLE PHONG
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaPhong, MaCN, MaLP, SoPhong, Tang, TrangThai);

-- 9. DAT_PHONG
LOAD DATA LOCAL INFILE 'data/csv/dat_phong.csv'
INTO TABLE DAT_PHONG
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaDP, MaKH, NgayDat, TrangThai, @v_GhiChu)
SET GhiChu = NULLIF(@v_GhiChu, '');

-- 10. NHAN_VIEN
LOAD DATA LOCAL INFILE 'data/csv/nhan_vien.csv'
INTO TABLE NHAN_VIEN
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaNV, MaCN, HoTen, SDT, @v_Email, ChucVu, NgayVaoLam)
SET Email = NULLIF(@v_Email, '');

-- 11. DV_CHI_NHANH
LOAD DATA LOCAL INFILE 'data/csv/dv_chi_nhanh.csv'
INTO TABLE DV_CHI_NHANH
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaCN, MaDV, DonGia, TrangThai);

-- 12. GOI_COMBO
LOAD DATA LOCAL INFILE 'data/csv/goi_combo.csv'
INTO TABLE GOI_COMBO
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaCombo, MaCN, MaLP, TenCombo, SoNgayLuuTru, BaoGomVeVuiChoi, BaoGomBuffet, BaoGomDonSanBay, GiaGoi, @v_MoTa)
SET MoTa = NULLIF(@v_MoTa, '');

-- 13. LOAI_VE
LOAD DATA LOCAL INFILE 'data/csv/loai_ve.csv'
INTO TABLE LOAI_VE
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaLoaiVe, MaKhu, TenLoaiVe, DoiTuong, GiaVe, @v_KhungGio, @v_MoTa)
SET KhungGio = NULLIF(@v_KhungGio, ''),
    MoTa = NULLIF(@v_MoTa, '');

-- 14. CT_DAT_PHONG
LOAD DATA LOCAL INFILE 'data/csv/ct_dat_phong.csv'
INTO TABLE CT_DAT_PHONG
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaCTDP, MaDP, MaPhong, NgayCheckIn, NgayCheckOut, GiaThoaThuan);

-- 15. PHAN_CA
LOAD DATA LOCAL INFILE 'data/csv/phan_ca.csv'
INTO TABLE PHAN_CA
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaPhanCa, MaNV, MaCa, NgayLam);

-- 16. HOA_DON
LOAD DATA LOCAL INFILE 'data/csv/hoa_don.csv'
INTO TABLE HOA_DON
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaHD, MaDP, NgayLap, TongTien, TienCoc, TrangThai);

-- 17. CT_HOA_DON
LOAD DATA LOCAL INFILE 'data/csv/ct_hoa_don.csv'
INTO TABLE CT_HOA_DON
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaCTHD, MaHD, LoaiKhoanThu, MoTa, SoLuong, DonGia);

-- 18. GIAO_DICH_THANH_TOAN
LOAD DATA LOCAL INFILE 'data/csv/giao_dich_thanh_toan.csv'
INTO TABLE GIAO_DICH_THANH_TOAN
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaGiaoDich, MaHD, CongThanhToan, @v_MaGiaoDichCong, SoTien, ThoiGianGD, TrangThai, @v_NoiDungChuyenKhoan)
SET MaGiaoDichCong = NULLIF(@v_MaGiaoDichCong, ''),
    NoiDungChuyenKhoan = NULLIF(@v_NoiDungChuyenKhoan, '');

-- 19. SU_DUNG_DV
LOAD DATA LOCAL INFILE 'data/csv/su_dung_dv.csv'
INTO TABLE SU_DUNG_DV
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaSD, MaDP, MaCN, MaDV, ThoiGianSD, SoLuong, DonGiaTaiThoiDiem);

-- 20. VE_DIEN_TU
LOAD DATA LOCAL INFILE 'data/csv/ve_dien_tu.csv'
INTO TABLE VE_DIEN_TU
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaVe, MaDP, MaKH, MaLoaiVe, MaQR, NgaySuDung, GiaTien, TrangThai, @v_ThoiGianQuet)
SET ThoiGianQuet = NULLIF(@v_ThoiGianQuet, '');

-- 21. MA_GIAM_GIA
LOAD DATA LOCAL INFILE 'data/csv/ma_giam_gia.csv'
INTO TABLE MA_GIAM_GIA
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaVoucher, Code, LoaiGiam, GiaTriGiam, DonHangToiThieu, @v_GiamToiDa, SoLuongPhatHanh, SoLuongDaDung, NgayBatDau, NgayKetThuc, TrangThai)
SET GiamToiDa = NULLIF(@v_GiamToiDa, '');
