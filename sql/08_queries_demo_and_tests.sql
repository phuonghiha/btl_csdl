-- =============================================================================
-- 08_queries_demo_and_tests.sql
-- Bo truy van bao cao phan tich va kich ban kiem thu trigger/procedure/transaction
-- Yeu cau: da chay 01..07
-- =============================================================================

USE quan_ly_khach_san;
SET NAMES utf8mb4;

-- =============================================================================
-- PHAN A: 10 TRUY VAN BAO CAO PHAN TICH NGHIEP VU
-- =============================================================================

-- Q1. Xep hang doanh thu tong theo chi nhanh (su dung VIEW chong cong trung + WINDOW FUNCTION)
SELECT
    MaCN,
    TenCN,
    SUM(SoHoaDon) AS TongSoHoaDon,
    SUM(TongTienHoaDon) AS TongDoanhThu,
    SUM(TongTienDaThu) AS TongDaThu,
    DENSE_RANK() OVER (ORDER BY SUM(TongTienHoaDon) DESC) AS HangDoanhThu
FROM vw_doanh_thu_chi_nhanh
GROUP BY MaCN, TenCN
ORDER BY HangDoanhThu, MaCN;

-- Q2. Cong suat phong hien tai va ty le dang su dung tai tung chi nhanh
SELECT * FROM vw_cong_suat_phong_chi_nhanh ORDER BY TyLeDangSuDungPct DESC, MaCN;

-- Q3. Thong ke doanh thu & so dem thue theo loai phong
SELECT
    lp.MaLP,
    lp.TenLP,
    COUNT(ctdp.MaCTDP) AS SoLuotDatPhong,
    SUM(DATEDIFF(ctdp.NgayCheckOut, ctdp.NgayCheckIn)) AS TongSoDem,
    SUM(ctdp.GiaThoaThuan) AS TongDoanhThuPhong,
    ROUND(AVG(ctdp.GiaThoaThuan / DATEDIFF(ctdp.NgayCheckOut, ctdp.NgayCheckIn)), 2) AS DonGiaTrungBinhMoiDem
FROM LOAI_PHONG lp
LEFT JOIN PHONG p ON p.MaLP = lp.MaLP
LEFT JOIN CT_DAT_PHONG ctdp ON ctdp.MaPhong = p.MaPhong
GROUP BY lp.MaLP, lp.TenLP
ORDER BY TongDoanhThuPhong DESC;

-- Q4. Top 10 khach hang chi tieu cao nhat (chi tinh giao dich thanh cong)
WITH kh_chitieu AS (
    SELECT
        kh.MaKH,
        kh.HoTen,
        kh.SDT,
        COUNT(DISTINCT dp.MaDP) AS SoDonDat,
        COALESCE(SUM(CASE WHEN gd.TrangThai = 'Thành công' THEN gd.SoTien ELSE 0 END), 0) AS TongChiTieu
    FROM KHACH_HANG kh
    LEFT JOIN DAT_PHONG dp ON dp.MaKH = kh.MaKH
    LEFT JOIN HOA_DON hd ON hd.MaDP = dp.MaDP
    LEFT JOIN GIAO_DICH_THANH_TOAN gd ON gd.MaHD = hd.MaHD
    GROUP BY kh.MaKH, kh.HoTen, kh.SDT
)
SELECT
    MaKH,
    HoTen,
    SDT,
    SoDonDat,
    TongChiTieu,
    DENSE_RANK() OVER (ORDER BY TongChiTieu DESC) AS XepHangVIP
FROM kh_chitieu
ORDER BY TongChiTieu DESC, MaKH
LIMIT 10;

-- Q5. Thong ke dich vu duoc su dung nhieu nhat toan he thong
SELECT
    MaDV,
    TenDV,
    LoaiDV,
    SUM(SoLuotSuDung) AS TongLuot,
    SUM(TongSoLuong) AS TongSoLuong,
    SUM(TongDoanhThuDV) AS TongDoanhThu
FROM vw_su_dung_dich_vu_chi_tiet
GROUP BY MaDV, TenDV, LoaiDV
ORDER BY TongDoanhThu DESC, TongLuot DESC;

-- Q6. Thong ke gio cong phan ca cua nhan vien trong thang 07/2025
--     (xu ly chinh xac ca qua dem nhu Ca 3: 22:00:00 -> 06:30:00)
SELECT
    cn.MaCN,
    cn.TenCN,
    nv.MaNV,
    nv.HoTen,
    nv.ChucVu,
    COUNT(pc.MaPhanCa) AS SoCaLam,
    ROUND(SUM(
        CASE
            WHEN cl.GioKT >= cl.GioBD
                THEN TIME_TO_SEC(TIMEDIFF(cl.GioKT, cl.GioBD)) / 3600.0
            ELSE (86400 - TIME_TO_SEC(cl.GioBD) + TIME_TO_SEC(cl.GioKT)) / 3600.0
        END
    ), 2) AS TongSoGioPhanCa
FROM PHAN_CA pc
JOIN NHAN_VIEN nv ON nv.MaNV = pc.MaNV
JOIN CHI_NHANH cn ON cn.MaCN = nv.MaCN
JOIN CA_LAM cl ON cl.MaCa = pc.MaCa
WHERE pc.NgayLam BETWEEN '2025-07-01' AND '2025-07-31'
GROUP BY cn.MaCN, cn.TenCN, nv.MaNV, nv.HoTen, nv.ChucVu
ORDER BY cn.MaCN, TongSoGioPhanCa DESC, nv.MaNV;

-- Q7. Tinh hinh su dung ve dien tu QR theo khu vui choi
SELECT
    kv.MaKhu,
    kv.TenKhu,
    cn.TenCN,
    COUNT(ve.MaVe) AS TongSoVe,
    SUM(CASE WHEN ve.TrangThai = 'Đã sử dụng' THEN 1 ELSE 0 END) AS SoVeDaQuet,
    SUM(CASE WHEN ve.TrangThai = 'Chưa sử dụng' THEN 1 ELSE 0 END) AS SoVeChuaDung,
    SUM(CASE WHEN ve.TrangThai = 'Hết hạn' THEN 1 ELSE 0 END) AS SoVeHetHan,
    COALESCE(SUM(ve.GiaTien), 0) AS TongGiaTriVe
FROM KHU_VUI_CHOI kv
JOIN CHI_NHANH cn ON cn.MaCN = kv.MaCN
LEFT JOIN LOAI_VE lv ON lv.MaKhu = kv.MaKhu
LEFT JOIN VE_DIEN_TU ve ON ve.MaLoaiVe = lv.MaLoaiVe
GROUP BY kv.MaKhu, kv.TenKhu, cn.TenCN
ORDER BY TongSoVe DESC, kv.MaKhu;

-- Q8. Theo doi ty le su dung ma giam gia
SELECT
    Code,
    LoaiGiam,
    GiaTriGiam,
    SoLuongPhatHanh,
    SoLuongDaDung,
    (SoLuongPhatHanh - SoLuongDaDung) AS SoLuongConLai,
    ROUND(100.0 * SoLuongDaDung / NULLIF(SoLuongPhatHanh, 0), 2) AS TyLeSuDungPct,
    NgayBatDau,
    NgayKetThuc,
    TrangThai
FROM MA_GIAM_GIA
ORDER BY TyLeSuDungPct DESC, Code;

-- Q9. Doi chieu cac don dat nhieu phong (kiem tra tinh toan ven don dat phong)
SELECT
    dp.MaDP,
    kh.HoTen,
    COUNT(ctdp.MaCTDP) AS SoPhongTrongDon,
    SUM(ctdp.GiaThoaThuan) AS TongTienPhong,
    hd.TongTien AS TongTienHoaDon,
    (hd.TongTien - SUM(ctdp.GiaThoaThuan)) AS KhoanKhac_DichVu
FROM DAT_PHONG dp
JOIN KHACH_HANG kh ON kh.MaKH = dp.MaKH
JOIN CT_DAT_PHONG ctdp ON ctdp.MaDP = dp.MaDP
JOIN HOA_DON hd ON hd.MaDP = dp.MaDP
GROUP BY dp.MaDP, kh.HoTen, hd.TongTien
HAVING COUNT(ctdp.MaCTDP) > 1 OR hd.TongTien <> SUM(ctdp.GiaThoaThuan)
ORDER BY SoPhongTrongDon DESC, dp.MaDP;

-- Q10. Kiem tra ma tran vai tro - quyen da duoc khoi tao trong RBAC
SELECT
    vt.MaCode AS VaiTro,
    vt.TenVaiTro,
    COUNT(vtq.MaQuyen) AS SoQuyen,
    GROUP_CONCAT(q.MaCode ORDER BY q.MaCode SEPARATOR ', ') AS DanhSachQuyen
FROM VAI_TRO vt
LEFT JOIN VAI_TRO_QUYEN vtq ON vtq.MaVaiTro = vt.MaVaiTro
LEFT JOIN QUYEN q ON q.MaQuyen = vtq.MaQuyen
GROUP BY vt.MaVaiTro, vt.MaCode, vt.TenVaiTro
ORDER BY vt.MaVaiTro;

-- =============================================================================
-- PHAN B: KICH BAN KIEM THU (DEMO CHAY THU PROCEDURE, TRIGGER, TRANSACTION)
-- =============================================================================

-- Test 1: Tim phong trong tai Chi nhanh 1 (Ha Noi) tu 2025-05-10 den 2025-05-13 cho 2 nguoi.
-- Ky vong: Phong MaPhong=1 (Bao tri) va MaPhong=2 (da co MaDP=1 dat 2025-05-10..2025-05-13) se BI LOAI;
--          Phong MaPhong=3 (SoPhong=103, TrangThai=Trong) se XUAT HIEN trong ket qua.
CALL sp_tim_phong_trong(1, '2025-05-10', '2025-05-13', 2);

-- Test 2: Kiem tra ham tinh gia mua & le co dinh (mua He M03 ngay 2025-07-15 vs le 01-01)
SELECT
    fn_gia_phong_theo_ngay('LP001', '2025-07-15') AS GiaLP001_MuaHe,
    fn_gia_phong_theo_ngay('LP001', '2025-01-01') AS GiaLP001_LeTetDuongLich,
    fn_gia_phong_theo_ngay('LP001', '2025-02-15') AS GiaLP001_MuaDong;

-- Test 3 (Kiem thu chan dat trung - se BAO LOI 45000 tu Trigger/Procedure, dung de minh hoa khi bao cao):
-- Bo comment 2 dong duoi day de kiem chung trigger/procedure tu choi dat trung phong MaPhong=2 (da co MaDP=1):
-- CALL sp_tao_dat_phong(2, 2, '2025-05-11', '2025-05-14', 'Test trung lich', NULL, @out_dp, @out_hd);
-- Ky vong loi: ERROR 1644 (45000): Phong da co lich dat trung khoang ngay

-- Test 4 (Kiem thu quy trinh day du trong TRANSACTION va ROLLBACK de giu sach du lieu mau):
-- Co the chay thu khoi lenh duoi day khi demo quy trinh Tao dat phong -> Xac nhan -> Thanh toan:
/*
CALL sp_tao_dat_phong(2, 3, '2026-08-01', '2026-08-04', 'Demo BTL CSDL', NULL, @new_dp, @new_hd);
SELECT @new_dp AS MaDP_Moi, @new_hd AS MaHD_Moi;
SELECT * FROM DAT_PHONG WHERE MaDP = @new_dp;
SELECT * FROM HOA_DON WHERE MaHD = @new_hd;

CALL sp_xac_nhan_dat_phong(@new_dp, NULL);
SELECT * FROM DAT_PHONG WHERE MaDP = @new_dp;

CALL sp_ghi_nhan_thanh_toan(@new_hd, 'VNPAY', 'DEMO-VNPAY-001', 4500000.00, 'Thanh toan demo', NULL);
SELECT * FROM HOA_DON WHERE MaHD = @new_hd;
SELECT * FROM GIAO_DICH_THANH_TOAN WHERE MaHD = @new_hd;

-- Don dep du lieu demo sau khi trinh bay xong:
DELETE FROM GIAO_DICH_THANH_TOAN WHERE MaHD = @new_hd;
DELETE FROM CT_HOA_DON WHERE MaHD = @new_hd;
DELETE FROM HOA_DON WHERE MaHD = @new_hd;
DELETE FROM CT_DAT_PHONG WHERE MaDP = @new_dp;
DELETE FROM DAT_PHONG WHERE MaDP = @new_dp;
*/
