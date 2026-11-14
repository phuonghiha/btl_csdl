# Quan ly chuoi khach san

Bo ma nguon du lieu va SQL cho bai tap CSDL quan ly chuoi khach san.

## Cau truc
- `data/csv/`: 21 tep CSV nguon, giu nguyen du lieu va ma khoa.
- `sql/01_schema.sql`: tao 21 bang nghiep vu va 7 bang phan quyen.
- `sql/02_seed_rbac.sql`: du lieu khoi tao vai tro va quyen.
- `sql/03_triggers.sql`: rang buoc nghiep vu bang trigger.
- `sql/04_data_audit.sql`: truy van kiem tra tinh hop le sau khi import.
- `sql/05_import_order.md`: thu tu import va cach chay.

## Luu y
- Chay MySQL 8.0.16+ (CHECK duoc enforce).
- Ngay luu bang DATE/DATETIME theo ISO; hien thi DD/MM/YYYY bang DATE_FORMAT.
- Ngay mua trong BANG_GIA duoc luu dang CHAR(5), vi CSV nguon dung MM-DD.
- Du lieu mau khong phai du lieu khach hang/nhan vien that.
- Khong import du lieu truoc khi tao schema.
