-- =============================================================================
-- 09_seed_demo_accounts.sql
-- Du lieu tai khoan mau cho 5 vai tro RBAC phuc vu kiem thu & demo BTL.
-- LUU Y BAO MAT: Chi su dung cho moi truong hoc tap/demo, KHONG dung cho production.
-- Yeu cau: da chay 01_schema.sql, 06_import_csv.sql, 02_seed_rbac.sql, 07_views_and_procedures.sql
-- =============================================================================

USE quan_ly_khach_san;
SET NAMES utf8mb4;

-- Mat khau demo truoc khi bam (chi ghi chu de test): 'Demo@123456'
-- Luu trong bang duoi dang SHA-256 (khong luu mat khau thuan).

INSERT INTO TAI_KHOAN (TenDangNhap, MatKhauHash, Email, TrangThai, MaNV, MaKH) VALUES
('admin_hethong', SHA2('Demo@123456', 256), 'nhanvien10.resort@gmail.com', 'Hoạt động', 10, NULL),
('quanly_cn1',    SHA2('Demo@123456', 256), 'nhanvien7.resort@gmail.com',  'Hoạt động', 5,  NULL),
('letan_cn1',     SHA2('Demo@123456', 256), 'nhanvien2.resort@gmail.com',  'Hoạt động', 1,  NULL),
('dichvu_cn2',    SHA2('Demo@123456', 256), 'nhanvien12.resort@gmail.com', 'Hoạt động', 14, NULL),
('khach_an',      SHA2('Demo@123456', 256), 'an.nguyen@vipclient.com',     'Hoạt động', NULL, 1);

-- Gan vai tro cho 5 tai khoan vua tao
INSERT INTO TAI_KHOAN_VAI_TRO (MaTK, MaVaiTro, MaNguoiGan)
SELECT tk.MaTK, vt.MaVaiTro, (SELECT MaTK FROM TAI_KHOAN WHERE TenDangNhap = 'admin_hethong')
FROM TAI_KHOAN tk
JOIN VAI_TRO vt ON (
    (tk.TenDangNhap = 'admin_hethong' AND vt.MaCode = 'ADMIN')
    OR (tk.TenDangNhap = 'quanly_cn1' AND vt.MaCode = 'QUAN_LY_CHI_NHANH')
    OR (tk.TenDangNhap = 'letan_cn1'  AND vt.MaCode = 'LE_TAN')
    OR (tk.TenDangNhap = 'dichvu_cn2' AND vt.MaCode = 'NHAN_VIEN_DICH_VU')
    OR (tk.TenDangNhap = 'khach_an'   AND vt.MaCode = 'KHACH_HANG')
);

-- Phan cong pham vi chi nhanh cho tai khoan nhan vien nghiep vu theo chi nhanh
INSERT INTO PHAN_CONG_CHI_NHANH (MaTK, MaCN, VaiTroTaiCN, NgayBatDau, NgayKetThuc)
SELECT tk.MaTK, 1, 'QUAN_LY_CHI_NHANH', '2025-01-01', NULL
FROM TAI_KHOAN tk WHERE tk.TenDangNhap = 'quanly_cn1'
UNION ALL
SELECT tk.MaTK, 1, 'LE_TAN', '2025-01-01', NULL
FROM TAI_KHOAN tk WHERE tk.TenDangNhap = 'letan_cn1'
UNION ALL
SELECT tk.MaTK, 2, 'NHAN_VIEN_DICH_VU', '2025-01-01', NULL
FROM TAI_KHOAN tk WHERE tk.TenDangNhap = 'dichvu_cn2';

-- Ghi nhan nhat ky khoi tao tai khoan mau
INSERT INTO NHAT_KY_HOAT_DONG (MaTK, HanhDong, BangDuLieu, KhoaBanGhi, GiaTriMoi, LyDo)
SELECT
    tk.MaTK,
    'KHOI_TAO_RBAC_MAU',
    'TAI_KHOAN',
    CAST(tk.MaTK AS CHAR),
    JSON_OBJECT('TaiKhoanDemo', 5),
    'Khoi tao 5 tai khoan demo phuc vu kiem thu phan quyen'
FROM TAI_KHOAN tk WHERE tk.TenDangNhap = 'admin_hethong';

-- Kiem tra lai ket qua phan quyen qua VIEW va truy van kiem toan so 8
SELECT
    TenDangNhap,
    MaVaiTro,
    MaChiNhanhDuocGiao,
    COUNT(MaQuyen) AS SoQuyenDuocCap
FROM vw_phan_quyen_tai_khoan
GROUP BY TenDangNhap, MaVaiTro, MaChiNhanhDuocGiao
ORDER BY TenDangNhap;

SELECT t.MaTK, t.TenDangNhap
FROM TAI_KHOAN t
LEFT JOIN TAI_KHOAN_VAI_TRO tv ON tv.MaTK = t.MaTK
WHERE tv.MaTK IS NULL;
