# Hướng dẫn tạo bảng và nhập dữ liệu CSV

Tài liệu này hướng dẫn thực hiện theo thứ tự để tạo cơ sở dữ liệu khách sạn, nhập dữ liệu mẫu, khởi tạo phân quyền và kiểm tra dữ liệu bằng MySQL.

## 1. Chuẩn bị

- Cài đặt MySQL 8.0.16 trở lên.
- Tải (clone) repository về máy tính.
- Mở MySQL Workbench hoặc công cụ quản lý MySQL mà bạn đang sử dụng.
- Nếu dùng lệnh `LOAD DATA LOCAL INFILE`, hãy bật tùy chọn cho phép nhập tệp cục bộ (`LOCAL INFILE`) trong cả máy chủ MySQL và ứng dụng kết nối.

## 2. Tạo cơ sở dữ liệu và các bảng

Mở tệp `sql/01_schema.sql`, sau đó chạy toàn bộ nội dung.

Tệp này tạo cơ sở dữ liệu `quan_ly_khach_san`, gồm:
- 21 bảng phục vụ nghiệp vụ khách sạn.
- 7 bảng phục vụ quản lý tài khoản, vai trò, quyền, phạm vi chi nhánh và nhật ký hoạt động.

Chỉ chuyển sang bước tiếp theo khi lệnh tạo bảng chạy thành công.

## 3. Nhập 21 tệp CSV nghiệp vụ

Các tệp CSV nằm trong thư mục `data/csv/`. Cần nhập theo đúng thứ tự dưới đây để bảng được tham chiếu đã có dữ liệu trước khi nhập bảng phụ thuộc.

| Thứ tự | Tệp CSV | Bảng MySQL |
|---:|---|---|
| 1 | `chi_nhanh.csv` | `CHI_NHANH` |
| 2 | `loai_phong.csv` | `LOAI_PHONG` |
| 3 | `khach_hang.csv` | `KHACH_HANG` |
| 4 | `dich_vu.csv` | `DICH_VU` |
| 5 | `ca_lam.csv` | `CA_LAM` |
| 6 | `khu_vui_choi.csv` | `KHU_VUI_CHOI` |
| 7 | `bang_gia.csv` | `BANG_GIA` |
| 8 | `phong.csv` | `PHONG` |
| 9 | `dat_phong.csv` | `DAT_PHONG` |
| 10 | `nhan_vien.csv` | `NHAN_VIEN` |
| 11 | `dv_chi_nhanh.csv` | `DV_CHI_NHANH` |
| 12 | `goi_combo.csv` | `GOI_COMBO` |
| 13 | `loai_ve.csv` | `LOAI_VE` |
| 14 | `ct_dat_phong.csv` | `CT_DAT_PHONG` |
| 15 | `phan_ca.csv` | `PHAN_CA` |
| 16 | `hoa_don.csv` | `HOA_DON` |
| 17 | `ct_hoa_don.csv` | `CT_HOA_DON` |
| 18 | `giao_dich_thanh_toan.csv` | `GIAO_DICH_THANH_TOAN` |
| 19 | `su_dung_dv.csv` | `SU_DUNG_DV` |
| 20 | `ve_dien_tu.csv` | `VE_DIEN_TU` |
| 21 | `ma_giam_gia.csv` | `MA_GIAM_GIA` |

### Ví dụ nhập một tệp CSV

Ví dụ dưới đây nhập dữ liệu từ `chi_nhanh.csv` vào bảng `CHI_NHANH`. Hãy chạy lệnh từ thư mục gốc của repository; nếu MySQL không tìm thấy tệp, hãy thay bằng đường dẫn tuyệt đối đến tệp trên máy của bạn.

> **Lưu ý về ký tự xuống dòng:** Toàn bộ các tệp CSV trong `data/csv/` hiện dùng chuẩn xuống dòng Windows (`\r\n`). Cần dùng `LINES TERMINATED BY '\r\n'` để tránh dính ký tự `\r` vào cột cuối cùng của mỗi dòng.

```sql
LOAD DATA LOCAL INFILE 'data/csv/chi_nhanh.csv'
INTO TABLE CHI_NHANH
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES;
```

Đối với bảng có ô trống cần chuyển thành `NULL` (như cột `ThoiGianQuet` trong `ve_dien_tu.csv`), cần đọc qua biến tạm và dùng `NULLIF(..., '')` để tránh lỗi `Incorrect datetime value: ''` ở chế độ strict của MySQL:

```sql
LOAD DATA LOCAL INFILE 'data/csv/ve_dien_tu.csv'
INTO TABLE VE_DIEN_TU
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\r\n'
IGNORE 1 LINES
(MaVe, MaDP, MaKH, MaLoaiVe, MaQR, NgaySuDung, GiaTien, TrangThai, @v_ThoiGianQuet)
SET ThoiGianQuet = NULLIF(@v_ThoiGianQuet, '');
```

Có thể dùng sẵn tập lệnh [sql/06_import_csv.sql](06_import_csv.sql) đã cấu hình đầy đủ thứ tự nhập, `LINES TERMINATED BY '\r\n'` và `NULLIF` cho cả 21 bảng nghiệp vụ (chỉ cần chỉnh lại đường dẫn nếu không chạy từ thư mục gốc của repository).

Với các tệp còn lại nếu nhập thủ công, thay tên tệp và tên bảng tương ứng theo bảng thứ tự ở trên. Trước khi nhập, cần bảo đảm thứ tự cột trong CSV trùng với thứ tự cột của bảng. Nếu thứ tự không trùng, hãy chỉ rõ danh sách cột trong câu lệnh nhập; không nhập trực tiếp theo vị trí mặc định.

### Quy tắc định dạng dữ liệu

- Các cột tiền và tỷ lệ đã được chuẩn hóa về 2 chữ số thập phân.
- Các cột Boolean trong `goi_combo.csv` sử dụng `1` và `0`.
- Các mã định danh và mã khóa ngoại được giữ nguyên; không tự ý đổi mã.
- Các cột kiểu `DATE` dùng định dạng `YYYY-MM-DD`.
- Các cột kiểu `DATETIME` dùng định dạng `YYYY-MM-DD HH:MM:SS`.
- Hai cột `BANG_GIA.NgayBD` và `BANG_GIA.NgayKT` được lưu dưới dạng chuỗi `VARCHAR(80)`. Dữ liệu có thể là `MM-DD` hoặc mô tả ngày lễ âm lịch, vì vậy không chuyển hai cột này thành kiểu `DATE`.
- Cột `VE_DIEN_TU.ThoiGianQuet` có thể để trống (`NULL`) và phải xử lý qua `NULLIF(..., '')` khi dùng `LOAD DATA LOCAL INFILE`.
- Ba tệp `loai_phong.csv`, `dich_vu.csv` và `khu_vui_choi.csv` có UTF-8 BOM ở đầu dòng tiêu đề. Khi dùng `LOAD DATA ... IGNORE 1 LINES`, dòng tiêu đề chứa BOM được bỏ qua tự động; nếu nhập bằng công cụ giao diện (như MySQL Workbench Wizard), cần kiểm tra ánh xạ cột đầu tiên để tránh lỗi tên cột dính ký tự BOM.
- `CT_DAT_PHONG.GiaThoaThuan` là tổng giá thỏa thuận cho toàn bộ thời gian lưu trú, không phải giá mỗi đêm.

**Lưu ý về giá trị trống:** Nếu CSV có ô trống ở cột cho phép NULL, hãy kiểm tra cách MySQL xử lý giá trị trống khi nhập. Không tự động thay ô trống bằng số 0 nếu ý nghĩa nghiệp vụ của nó là chưa có dữ liệu.

## 4. Khởi tạo dữ liệu phân quyền

Sau khi đã tạo bảng và nhập dữ liệu nghiệp vụ, mở và chạy `sql/02_seed_rbac.sql`.

Tệp này thêm các vai trò và quyền mẫu, đồng thời liên kết quyền với từng vai trò. Không có tài khoản đăng nhập mặc định được tạo sẵn.

Thư mục `data/csv/phan_quyen/` chứa các tệp CSV liên quan đến phân quyền:

| Tệp CSV | Mục đích |
|---|---|
| `vai_tro.csv` | Danh sách vai trò |
| `quyen.csv` | Danh sách quyền |
| `vai_tro_quyen.csv` | Gán quyền cho vai trò |
| `tai_khoan.csv` | Thông tin tài khoản |
| `tai_khoan_vai_tro.csv` | Gán vai trò cho tài khoản |
| `phan_cong_chi_nhanh.csv` | Phân công tài khoản vào chi nhánh |
| `nhat_ky_hoat_dong.csv` | Nhật ký thao tác |

Hiện các tệp vai trò, quyền và liên kết vai trò-quyền có dữ liệu mẫu; các tệp tài khoản, gán vai trò, phân công chi nhánh và nhật ký chỉ có dòng tiêu đề. Chỉ nhập dữ liệu tài khoản khi đã có tài khoản hợp lệ và mật khẩu đã được băm (hash) an toàn. Không lưu mật khẩu dạng văn bản thuần trong CSV.

Nếu đã chạy `02_seed_rbac.sql`, không nhập lại các CSV vai trò/quyền nếu chưa kiểm tra khả năng trùng khóa hoặc trùng mã.

## 5. Tạo trigger

Sau khi nhập xong dữ liệu, chạy toàn bộ tệp `sql/03_triggers.sql`.

Các trigger hỗ trợ kiểm soát một số quy tắc nghiệp vụ, chẳng hạn kiểm tra đặt trùng phòng và cập nhật tổng tiền hóa đơn. Tạo trigger sau khi nhập dữ liệu mẫu giúp tránh việc trigger can thiệp trong quá trình nạp dữ liệu ban đầu.

## 6. Kiểm tra dữ liệu

Chạy các câu truy vấn trong `sql/04_data_audit.sql`.

Đọc kết quả để kiểm tra:
- Số lượng bản ghi của từng bảng.
- Các khóa ngoại hoặc dữ liệu tham chiếu không hợp lệ.
- Các lượt đặt phòng có thời gian bị chồng lấn.
- Việc sử dụng dịch vụ, thanh toán và tổng tiền hóa đơn.
- Tình trạng vé và dữ liệu phân quyền.

Nếu truy vấn kiểm tra trả về bản ghi bất thường, hãy xác minh nguyên nhân trước khi sửa. Không xóa dữ liệu lịch sử chỉ để làm cho truy vấn kiểm tra không còn kết quả.

## 7. Phân quyền theo chi nhánh

- Bảng `TAI_KHOAN_VAI_TRO` lưu vai trò được gán cho từng tài khoản.
- Bảng `VAI_TRO_QUYEN` xác định mỗi vai trò được sử dụng những quyền nào.
- Bảng `PHAN_CONG_CHI_NHANH` xác định tài khoản được thao tác tại chi nhánh nào và trong khoảng thời gian nào.
- Việc có một vai trò không đồng nghĩa với việc được truy cập mọi chi nhánh. Backend cần kiểm tra cả quyền và phạm vi chi nhánh trước khi xử lý API.
- Tài khoản Admin có phạm vi toàn hệ thống theo quy tắc phân quyền của ứng dụng.
- Chức vụ ghi trong bảng `NHAN_VIEN` không tự động cấp quyền hệ thống; quyền phải được gán thông qua các bảng phân quyền.
