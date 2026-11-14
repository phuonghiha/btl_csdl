# Cơ sở dữ liệu quản lý chuỗi khách sạn

Kho lưu trữ này gồm dữ liệu mẫu dạng CSV và các tập lệnh SQL phục vụ bài tập thiết kế, tạo lập và kiểm tra cơ sở dữ liệu quản lý chuỗi khách sạn.

## 1. Cấu trúc thư mục

- `data/csv/`: 21 tệp CSV chứa dữ liệu nghiệp vụ khách sạn.
- `data/csv/phan_quyen/`: 7 tệp CSV phục vụ khởi tạo dữ liệu phân quyền (RBAC).
- `sql/01_schema.sql`: tạo cơ sở dữ liệu, 21 bảng nghiệp vụ và 7 bảng phân quyền.
- `sql/02_seed_rbac.sql`: thêm dữ liệu ban đầu cho vai trò, quyền và quan hệ giữa chúng.
- `sql/03_triggers.sql`: tạo các trigger kiểm soát một số quy tắc nghiệp vụ.
- `sql/04_data_audit.sql`: các câu truy vấn kiểm tra dữ liệu sau khi nhập.
- `sql/05_import_order.md`: hướng dẫn thứ tự và cách nhập dữ liệu CSV.

## 2. Công nghệ và yêu cầu

- MySQL 8.0.16 trở lên.
- Sử dụng InnoDB để hỗ trợ khóa ngoại và giao dịch.
- Nếu nhập dữ liệu bằng `LOAD DATA LOCAL INFILE`, cần cho phép tùy chọn `LOCAL INFILE` trên cả MySQL Server và công cụ kết nối.

## 3. Một số quy ước dữ liệu

- Các cột ngày có kiểu `DATE` hoặc `DATETIME` được lưu theo định dạng chuẩn MySQL, ví dụ `2025-05-10` hoặc `2025-05-10 14:30:00`.
- Khi hiển thị ngày theo định dạng ngày/tháng/năm, sử dụng `DATE_FORMAT(ten_cot, '%d/%m/%Y')`.
- Hai cột `BANG_GIA.NgayBD` và `BANG_GIA.NgayKT` dùng `VARCHAR(80)`, vì dữ liệu nguồn có cả giá trị dạng tháng-ngày (`MM-DD`) và mô tả ngày lễ âm lịch.
- Các giá trị tiền tệ sử dụng kiểu `DECIMAL`; không nên lưu tiền bằng kiểu số thực `FLOAT` hoặc `DOUBLE`.
- Dữ liệu trong kho là dữ liệu mẫu, không phải thông tin thật của khách hàng hoặc nhân viên.

## 4. Thứ tự triển khai

1. Chạy `sql/01_schema.sql` để tạo cơ sở dữ liệu và các bảng.
2. Nhập 21 tệp CSV nghiệp vụ theo thứ tự trong `sql/05_import_order.md`.
3. Chạy `sql/02_seed_rbac.sql` để khởi tạo vai trò và quyền.
4. Nếu sử dụng các tệp CSV phân quyền, nhập chúng theo hướng dẫn tương ứng và bảo đảm mã khóa chính, khóa ngoại khớp với dữ liệu tài khoản thực tế.
5. Chạy `sql/03_triggers.sql` để tạo trigger.
6. Chạy `sql/04_data_audit.sql` để kiểm tra dữ liệu.

**Lưu ý:** Không nhập CSV trước khi tạo bảng. Không tự ý sửa mã định danh hoặc mã khóa ngoại nếu chưa kiểm tra các bảng liên quan.
