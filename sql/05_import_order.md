# Cach nap du lieu va kich hoat rang buoc

## Yeu cau
- MySQL 8.0.16 tro len.
- Bat LOCAL INFILE trong MySQL Workbench/Client neu dung LOAD DATA LOCAL INFILE.
- Clone repo ve may, mo thu muc goc cua repo.

## Thu tu thuc hien
1. Chay `sql/01_schema.sql` de tao database, 21 bang nghiep vu va 7 bang RBAC.
2. Import 21 CSV theo dung thu tu ben duoi. Dung `LOAD DATA LOCAL INFILE`, bo qua dong header.
3. Chay `sql/02_seed_rbac.sql` de tao 5 vai tro va bo quyen.
4. Chay `sql/03_triggers.sql` sau khi import xong, tranh trigger tac dong vao qua trinh nap du lieu mau.
5. Chay `sql/04_data_audit.sql` va xem cac truy van kiem tra co tra ve ban ghi bat thuong hay khong.

## Thu tu import CSV
Thu tu nay dam bao bang duoc tham chieu da co truoc khi nap bang con:
1. chi_nhanh.csv
2. loai_phong.csv
3. khach_hang.csv
4. dich_vu.csv
5. ca_lam.csv
6. khu_vui_choi.csv
7. bang_gia.csv
8. phong.csv
9. dat_phong.csv
10. nhan_vien.csv
11. dv_chi_nhanh.csv
12. goi_combo.csv
13. loai_ve.csv
14. ct_dat_phong.csv
15. phan_ca.csv
16. hoa_don.csv
17. ct_hoa_don.csv
18. giao_dich_thanh_toan.csv
19. su_dung_dv.csv
20. ve_dien_tu.csv
21. ma_giam_gia.csv

## Mau lenh import
Chay lenh tu thu muc goc repo, thay ten tep va bang tuong ung theo danh sach. Neu MySQL Server khong cho phep duong dan tuong doi, hay dung duong dan tuyet doi tren may.

```sql
LOAD DATA LOCAL INFILE 'data/csv/chi_nhanh.csv'
INTO TABLE CHI_NHANH
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;
```

Voi cac tep khac, thay duong dan va ten bang tuong ung. CSV trong repo da duoc chuan hoa cac cot tien/ty le ve 2 chu so thap phan; cac cot boolean trong `goi_combo.csv` dung `1`/`0`. Ma khoa va ngay thang duoc giu nguyen, khong tu sua ma khoa truoc khi import.

## Luu y quan trong
- `MaLP` la VARCHAR (LP001-LP006), khong phai so nguyen.
- `MaMua` va `MaSuKienLe` la ma danh muc dang chuoi; khong ep thanh so.
- `BANG_GIA.NgayBD/NgayKT` la `VARCHAR(80)`: phan lon gia tri la `MM-DD`, nhung mot so dong la mo ta ngay le am lich; khong ep cot nay thanh DATE hoac CHAR(5).
- Cac cot ngay khac duoc luu DATE/DATETIME theo ISO trong CSV; hien thi theo ngay/thang/nam bang `DATE_FORMAT(cot,'%d/%m/%Y')`.
- `VE_DIEN_TU.ThoiGianQuet` cho phep NULL.
- `CT_DAT_PHONG.GiaThoaThuan` la gia thoa thuan cho ca thoi gian luu tru theo mo ta bo du lieu; khong nhan them so dem.
- Khong tao tai khoan voi mat khau mac dinh. Tao tai khoan qua backend va luu mat khau da bam hash.
- Sau import, doi chieu so dong voi README. Truy van audit co the tra ve dong neu co sai lech; khong tu dong xoa du lieu lich su.

## Phan quyen theo chi nhanh
Gan role trong `TAI_KHOAN_VAI_TRO`; gan pham vi chi nhanh trong `PHAN_CONG_CHI_NHANH`. Role khong tu dong cap quyen tren moi chi nhanh. Moi API nhan MaCN phai kiem tra user co phan cong con hieu luc cho MaCN do; Admin co quyen toan he thong. Chuc vu trong NHAN_VIEN khong tu dong dong nghia voi role.
