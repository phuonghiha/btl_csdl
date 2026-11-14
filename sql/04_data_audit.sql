USE quan_ly_khach_san;

-- 1. So luong ban ghi theo bo du lieu mau
SELECT 'CHI_NHANH' Bang,COUNT(*) SoDong FROM CHI_NHANH UNION ALL
SELECT 'PHONG',COUNT(*) FROM PHONG UNION ALL
SELECT 'LOAI_PHONG',COUNT(*) FROM LOAI_PHONG UNION ALL
SELECT 'BANG_GIA',COUNT(*) FROM BANG_GIA UNION ALL
SELECT 'KHACH_HANG',COUNT(*) FROM KHACH_HANG UNION ALL
SELECT 'DAT_PHONG',COUNT(*) FROM DAT_PHONG UNION ALL
SELECT 'CT_DAT_PHONG',COUNT(*) FROM CT_DAT_PHONG UNION ALL
SELECT 'NHAN_VIEN',COUNT(*) FROM NHAN_VIEN UNION ALL
SELECT 'CA_LAM',COUNT(*) FROM CA_LAM UNION ALL
SELECT 'PHAN_CA',COUNT(*) FROM PHAN_CA UNION ALL
SELECT 'DICH_VU',COUNT(*) FROM DICH_VU UNION ALL
SELECT 'DV_CHI_NHANH',COUNT(*) FROM DV_CHI_NHANH UNION ALL
SELECT 'SU_DUNG_DV',COUNT(*) FROM SU_DUNG_DV UNION ALL
SELECT 'HOA_DON',COUNT(*) FROM HOA_DON UNION ALL
SELECT 'CT_HOA_DON',COUNT(*) FROM CT_HOA_DON UNION ALL
SELECT 'GIAO_DICH_THANH_TOAN',COUNT(*) FROM GIAO_DICH_THANH_TOAN UNION ALL
SELECT 'GOI_COMBO',COUNT(*) FROM GOI_COMBO UNION ALL
SELECT 'KHU_VUI_CHOI',COUNT(*) FROM KHU_VUI_CHOI UNION ALL
SELECT 'LOAI_VE',COUNT(*) FROM LOAI_VE UNION ALL
SELECT 'VE_DIEN_TU',COUNT(*) FROM VE_DIEN_TU UNION ALL
SELECT 'MA_GIAM_GIA',COUNT(*) FROM MA_GIAM_GIA;

-- 2. Dat phong co ngay khong hop le
SELECT * FROM CT_DAT_PHONG WHERE NgayCheckOut<=NgayCheckIn;

-- 3. Cac khoang dat phong da xac nhan bi trung
SELECT a.MaCTDP,a.MaPhong,a.MaDP,b.MaCTDP MaCTDP_Trung,b.MaDP MaDP_Trung
FROM CT_DAT_PHONG a
JOIN DAT_PHONG da ON da.MaDP=a.MaDP AND da.TrangThai='Đã xác nhận'
JOIN CT_DAT_PHONG b ON b.MaPhong=a.MaPhong AND b.MaCTDP>a.MaCTDP
JOIN DAT_PHONG db ON db.MaDP=b.MaDP AND db.TrangThai='Đã xác nhận'
WHERE a.NgayCheckIn<b.NgayCheckOut AND a.NgayCheckOut>b.NgayCheckIn;

-- 4. Su dung dich vu ngoai khoang luu tru hoac khac chi nhanh cua phong dat
SELECT s.MaSD,s.MaDP,s.MaCN,s.MaDV,s.ThoiGianSD,c.NgayCheckIn,c.NgayCheckOut,p.MaCN MaCN_Phong
FROM SU_DUNG_DV s
JOIN CT_DAT_PHONG c ON c.MaDP=s.MaDP
JOIN PHONG p ON p.MaPhong=c.MaPhong
WHERE s.ThoiGianSD<c.NgayCheckIn
   OR s.ThoiGianSD>=c.NgayCheckOut
   OR s.MaCN<>p.MaCN;

-- 5. Tong chi tiet hoa don khac tong hoa don
SELECT h.MaHD,h.TongTien,COALESCE(SUM(c.SoLuong*c.DonGia),0) TongChiTiet
FROM HOA_DON h LEFT JOIN CT_HOA_DON c ON c.MaHD=h.MaHD
GROUP BY h.MaHD,h.TongTien
HAVING h.TongTien<>COALESCE(SUM(c.SoLuong*c.DonGia),0);

-- 6. Tong giao dich thanh cong va hoa don da thanh toan
SELECT h.MaHD,h.TongTien,
       COALESCE(SUM(CASE WHEN g.TrangThai='Thành công' THEN g.SoTien ELSE 0 END),0) TongDaThu
FROM HOA_DON h LEFT JOIN GIAO_DICH_THANH_TOAN g ON g.MaHD=h.MaHD
GROUP BY h.MaHD,h.TongTien,h.TrangThai
HAVING h.TrangThai='Đã thanh toán'
   AND ABS(h.TongTien-COALESCE(SUM(CASE WHEN g.TrangThai='Thành công' THEN g.SoTien ELSE 0 END),0))>0.01;

-- 7. Ve dien tu da quet nhung thieu thoi gian quet (hoac nguoc lai)
SELECT * FROM VE_DIEN_TU
WHERE (TrangThai='Đã sử dụng' AND ThoiGianQuet IS NULL)
   OR (TrangThai<>'Đã sử dụng' AND ThoiGianQuet IS NOT NULL);

-- 8. Tai khoan chua gan vai tro / tai khoan nhan vien chua phan cong chi nhanh
SELECT t.MaTK,t.TenDangNhap
FROM TAI_KHOAN t LEFT JOIN TAI_KHOAN_VAI_TRO tv ON tv.MaTK=t.MaTK
WHERE tv.MaTK IS NULL;
