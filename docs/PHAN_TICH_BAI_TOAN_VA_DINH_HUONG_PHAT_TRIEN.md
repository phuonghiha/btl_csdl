# Phân tích bài toán và định hướng phát triển website quản lý chuỗi khách sạn

> Tài liệu được tổng hợp từ **Đặc tả chức năng và nghiệp vụ – Website quản lý chuỗi khách sạn, phiên bản 1.0 ngày 12/11/2026** và đối chiếu với cấu trúc SQL/CSV hiện có trong repository.  
> Nội dung được chia thành: yêu cầu trong đặc tả, hiện trạng cơ sở dữ liệu và đề xuất triển khai. Các phần đề xuất không được hiểu là chức năng đã hoàn thành.

## 1. Tổng quan bài toán

Bài toán là xây dựng website quản lý tập trung hoạt động của một chuỗi khách sạn có nhiều chi nhánh. Hệ thống hỗ trợ quản lý phòng, giá, khách hàng, đặt phòng, dịch vụ, nhân viên, ca làm, hóa đơn, thanh toán, báo cáo và dashboard.

Mục tiêu chính:

- Tập trung dữ liệu của nhiều chi nhánh trên một hệ thống.
- Hỗ trợ khách hàng tra cứu và đặt phòng.
- Hỗ trợ nhân viên xử lý quy trình vận hành từ xác nhận đặt phòng đến check-in, sử dụng dịch vụ, check-out và thanh toán.
- Phân quyền theo vai trò, đồng thời giới hạn dữ liệu theo chi nhánh được phân công.
- Cung cấp báo cáo và dashboard phù hợp với từng nhóm người dùng.

**Ngoài phạm vi lõi theo đặc tả:** quản lý kho, kế toán tổng hợp, nhà cung cấp, chương trình khách hàng thân thiết, tích hợp khóa cửa và OTA. Có thể xem xét ở các giai đoạn sau.

## 2. Người dùng và phân quyền

| Vai trò | Phạm vi dữ liệu | Chức năng chính |
|---|---|---|
| Khách hàng | Hồ sơ và giao dịch của chính mình | Đăng ký/đăng nhập, tìm phòng, đặt phòng, xem/hủy yêu cầu, xem hóa đơn |
| Lễ tân | Một hoặc nhiều chi nhánh được phân công | Tra cứu, xác nhận đặt phòng theo quyền, check-in/out, ghi nhận dịch vụ, lập hóa đơn |
| Nhân viên dịch vụ | Dịch vụ và ca làm tại chi nhánh được phân công | Xem lịch ca, ghi nhận dịch vụ được giao |
| Quản lý chi nhánh | Chi nhánh được phụ trách | Quản lý phòng, giá, nhân viên, dịch vụ và báo cáo chi nhánh |
| Admin | Toàn hệ thống | Quản lý chi nhánh, tài khoản, vai trò, cấu hình và dashboard tổng |

### Nguyên tắc phân quyền

Không chỉ ẩn nút trên giao diện. Backend phải kiểm tra quyền ở từng API và kiểm tra phạm vi chi nhánh của bản ghi. Ví dụ, quản lý chi nhánh A không được xem hoặc sửa dữ liệu chi nhánh B bằng cách thay mã chi nhánh trong request.

Repository hiện có 7 bảng RBAC:

- `TAI_KHOAN`: tài khoản và mật khẩu đã băm.
- `VAI_TRO`: danh mục vai trò.
- `QUYEN`: danh mục quyền.
- `VAI_TRO_QUYEN`: quyền thuộc vai trò.
- `TAI_KHOAN_VAI_TRO`: vai trò được gán cho tài khoản.
- `PHAN_CONG_CHI_NHANH`: phạm vi chi nhánh được phân công.
- `NHAT_KY_HOAT_DONG`: nhật ký thao tác.

File `sql/02_seed_rbac.sql` hiện khai báo 5 vai trò và 20 quyền mẫu. Các CSV tài khoản, gán vai trò, phân công chi nhánh và nhật ký hiện chỉ có dòng tiêu đề; không có tài khoản mặc định.

## 3. Các khu vực chức năng của website

| Khu vực | Chức năng dự kiến |
|---|---|
| Tổng quan | Dashboard tổng hệ thống hoặc dashboard chi nhánh |
| Đặt phòng | Tìm phòng, danh sách/chi tiết đặt phòng, lịch phòng, check-in, check-out |
| Khách hàng | Hồ sơ, lịch sử lưu trú và đặt phòng |
| Quản lý phòng | Chi nhánh, loại phòng, phòng, bảng giá và khung giá |
| Dịch vụ | Danh mục dịch vụ, dịch vụ tại chi nhánh, lịch sử sử dụng |
| Nhân sự | Nhân viên, ca làm và lịch phân ca |
| Tài chính | Hóa đơn, chi tiết hóa đơn, thanh toán và công nợ |
| Báo cáo | Doanh thu, công suất phòng, đặt phòng, dịch vụ và nhân sự |
| Quản trị | Tài khoản, vai trò, quyền, cấu hình và nhật ký |

## 4. Quy trình nghiệp vụ chính

### 4.1. Quy trình đặt phòng và lưu trú

1. Khách chọn chi nhánh, ngày nhận phòng, ngày trả phòng, số người và số phòng.
2. Hệ thống kiểm tra sức chứa, trạng thái phòng, lịch đặt và lịch bảo trì/khóa bán.
3. Hệ thống hiển thị phòng phù hợp, loại phòng, tiện nghi, giá và chính sách.
4. Khách chọn phòng, cung cấp thông tin người lưu trú và gửi yêu cầu đặt phòng.
5. Hệ thống tính tạm tính, tiền cọc dự kiến và tạo đặt phòng ở trạng thái chờ xác nhận.
6. Lễ tân hoặc quản lý kiểm tra thông tin, khả dụng, giá và tiền cọc; sau đó xác nhận hoặc từ chối kèm lý do.
7. Khi khách đến, nhân viên kiểm tra thông tin và thực hiện check-in.
8. Trong thời gian lưu trú, nhân viên ghi nhận dịch vụ khách sử dụng.
9. Khi khách trả phòng, hệ thống tổng hợp tiền phòng, dịch vụ, phụ thu, giảm giá, tiền cọc và số tiền còn phải trả.
10. Nhân viên xác nhận check-out, lập/chốt hóa đơn và ghi nhận thanh toán.

### 4.2. Quy trình hủy đặt phòng

1. Khách gửi yêu cầu hủy theo chính sách.
2. Nhân viên có quyền kiểm tra yêu cầu.
3. Nhân viên xử lý, ghi nhận người thực hiện, thời điểm, lý do và phí hủy nếu có.
4. Hệ thống cập nhật trạng thái và giải phóng khả năng bán phòng theo quy tắc nghiệp vụ.

### 4.3. Quy trình dịch vụ

1. Quản lý cấu hình danh mục dịch vụ và dịch vụ được cung cấp tại từng chi nhánh.
2. Nhân viên chọn đặt phòng, dịch vụ, số lượng và thời điểm sử dụng.
3. Hệ thống lưu đơn giá tại thời điểm phát sinh.
4. Nếu điều chỉnh hoặc hủy dịch vụ, người thực hiện phải có quyền và ghi rõ lý do.

### 4.4. Quy trình nhân sự

1. Tạo hồ sơ nhân viên và xác định chi nhánh.
2. Khai báo ca làm, giờ bắt đầu, giờ kết thúc và quy tắc ca qua đêm.
3. Phân nhân viên vào ca/ngày/chi nhánh.
4. Kiểm tra không phân ca trùng thời gian.
5. Nhân viên xem lịch cá nhân; quản lý xem lịch toàn chi nhánh.

## 5. Quy tắc nghiệp vụ cần bảo đảm

- Ngày trả phòng phải sau ngày nhận phòng.
- Số khách không vượt sức chứa loại phòng, trừ trường hợp có quy định phụ thu.
- Phòng chỉ khả dụng nếu không có đặt phòng hợp lệ giao nhau với khoảng lưu trú và không bị bảo trì/khóa bán.
- Hai khoảng lưu trú giao nhau khi:

  `NgayCheckIn_moi < NgayCheckOut_cu AND NgayCheckOut_moi > NgayCheckIn_cu`

  Quy tắc này cho phép khách mới nhận phòng đúng ngày khách trước trả phòng.
- Không xóa vật lý khách hàng, đặt phòng, hóa đơn hoặc khoản thanh toán đã phát sinh; ưu tiên cập nhật trạng thái.
- Lưu snapshot đơn giá, tên dịch vụ và thông tin khoản thu tại thời điểm phát sinh.
- Tiền cọc phải có cơ sở tính rõ ràng; nếu áp dụng tỷ lệ 30% thì cần chốt tỷ lệ tính trên tiền phòng hay tổng hóa đơn.
- Dùng transaction cho các thao tác nhiều bước như xác nhận đặt phòng, check-in, check-out và chốt hóa đơn.
- Trigger không thay thế kiểm soát đồng thời ở backend; cần transaction/locking hoặc cơ chế giữ phòng.
- Trạng thái vận hành hiện tại của phòng không đồng nghĩa với khả năng bán phòng trong tương lai. Khả năng bán phải tính từ lịch đặt và lịch bảo trì.
- Báo cáo doanh thu phải thống nhất ghi nhận theo ngày lập hóa đơn, ngày thanh toán hay ngày hoàn tất lưu trú.

## 6. Đối chiếu với cơ sở dữ liệu hiện tại

Repository hiện có **21 bảng nghiệp vụ và 7 bảng RBAC**, tổng cộng 28 bảng.

### 6.1. Nhóm bảng nghiệp vụ

| Nhóm | Bảng |
|---|---|
| Chi nhánh và phòng | `CHI_NHANH`, `LOAI_PHONG`, `PHONG`, `BANG_GIA` |
| Khách hàng và đặt phòng | `KHACH_HANG`, `DAT_PHONG`, `CT_DAT_PHONG` |
| Dịch vụ | `DICH_VU`, `DV_CHI_NHANH`, `SU_DUNG_DV` |
| Nhân sự | `NHAN_VIEN`, `CA_LAM`, `PHAN_CA` |
| Tài chính | `HOA_DON`, `CT_HOA_DON`, `GIAO_DICH_THANH_TOAN` |
| Tiện ích/khuyến mại | `GOI_COMBO`, `KHU_VUI_CHOI`, `LOAI_VE`, `VE_DIEN_TU`, `MA_GIAM_GIA` |

### 6.2. Các điểm đã được mô hình hóa

- Một chi nhánh có nhiều phòng và nhân viên.
- Phòng thuộc một loại phòng và một chi nhánh.
- Một đặt phòng có thể có nhiều dòng chi tiết phòng thông qua `CT_DAT_PHONG`.
- Dịch vụ được cấu hình theo chi nhánh qua `DV_CHI_NHANH`.
- Lượt sử dụng dịch vụ lưu đơn giá tại thời điểm sử dụng qua `DonGiaTaiThoiDiem`.
- Hóa đơn có các dòng chi tiết và các giao dịch thanh toán.
- Tài khoản liên kết với hồ sơ nhân viên hoặc khách hàng; bảng RBAC quản lý vai trò, quyền và phạm vi chi nhánh.

### 6.3. Các điểm cần đối chiếu hoặc quyết định trước khi phát triển backend

| Nội dung | Hiện trạng trong schema | Việc cần làm |
|---|---|---|
| Nhiều phòng trong một đặt phòng | Có `DAT_PHONG` và `CT_DAT_PHONG` | Backend phải xử lý nhiều dòng phòng và kiểm tra trùng lịch cho từng phòng |
| Nhiều lần thanh toán | Có bảng `GIAO_DICH_THANH_TOAN` liên kết hóa đơn | Backend cần cộng các giao dịch hợp lệ, xử lý thanh toán thất bại/hoàn tiền |
| Nhiều hóa đơn cho một đặt phòng | `HOA_DON.MaDP` đang có ràng buộc UNIQUE | Hiện tại mỗi đặt phòng chỉ liên kết tối đa một hóa đơn; cần xác nhận có cần tách nhiều hóa đơn không |
| Tài khoản khách hàng/nhân viên | `TAI_KHOAN` có `MaKH` hoặc `MaNV` | Cần quy trình tạo tài khoản, băm mật khẩu, gán role và khóa/mở khóa |
| Phạm vi chi nhánh | Có `PHAN_CONG_CHI_NHANH` | Backend phải kiểm tra role và chi nhánh ở từng truy vấn/thao tác |
| Bảo trì phòng | Schema hiện có trạng thái phòng nhưng chưa thấy bảng lịch bảo trì riêng | Nếu cần đặt lịch bảo trì theo khoảng ngày, cần thiết kế bổ sung |
| Giá theo mùa/ngày | `BANG_GIA.NgayBD`, `NgayKT` đang là `VARCHAR(80)` do dữ liệu nguồn có cả MM-DD và mô tả ngày lễ âm lịch | Cần thống nhất cách diễn giải và truy vấn giá trước khi xây dựng tính giá tự động |
| Nhật ký và lý do hủy/điều chỉnh | Có bảng nhật ký hoạt động tổng quát | Backend cần ghi log đầy đủ người thao tác, thời điểm, dữ liệu cũ/mới và lý do |
| Dashboard | Có dữ liệu nền nhưng chưa có API/tầng tổng hợp | Xây dựng truy vấn tổng hợp và định nghĩa thống nhất cho từng KPI |

**Lưu ý về trạng thái hoàn thành:** repository hiện là dự án cơ sở dữ liệu gồm SQL và CSV. Chưa có căn cứ để kết luận website, giao diện, API, backend, dashboard hoặc quy trình nghiệp vụ đã được triển khai. Các script SQL và dữ liệu CSV cũng cần được chạy thử trên MySQL thực tế trước khi xác nhận nhập liệu thành công.

## 7. Các script SQL đang có

| Tệp | Vai trò |
|---|---|
| `sql/01_schema.sql` | Tạo database, 21 bảng nghiệp vụ, 7 bảng RBAC, khóa và chỉ mục |
| `sql/02_seed_rbac.sql` | Khởi tạo 5 vai trò, 20 quyền và các liên kết vai trò-quyền mẫu |
| `sql/03_triggers.sql` | Kiểm tra trùng lịch đặt phòng đã xác nhận và cập nhật tổng tiền hóa đơn từ chi tiết |
| `sql/04_data_audit.sql` | Các truy vấn rà soát dữ liệu |
| `sql/05_import_order.md` | Hướng dẫn thứ tự nhập CSV và khởi tạo dữ liệu |

Thứ tự tổng quát được README hướng dẫn: tạo schema → nhập CSV nghiệp vụ → khởi tạo RBAC → tạo trigger → chạy kiểm tra dữ liệu. Cần tuân thủ chi tiết trong `sql/05_import_order.md`.

## 8. Dashboard theo vai trò

### Admin – toàn hệ thống

- KPI: doanh thu, số chi nhánh hoạt động, tổng số phòng, số phòng đang có khách, số đặt phòng hôm nay và số đặt phòng chờ xác nhận.
- Biểu đồ doanh thu theo thời gian và chi nhánh.
- Tỷ lệ lấp đầy theo chi nhánh.
- Thống kê trạng thái đặt phòng.
- Top chi nhánh, loại phòng và dịch vụ.
- Cảnh báo đặt phòng sắp check-in, phòng bảo trì, hóa đơn chưa thanh toán và ca thiếu nhân viên.

### Quản lý chi nhánh

- Vận hành hôm nay: khách check-in/check-out, khách đang lưu trú, phòng cần dọn/bảo trì.
- Tình trạng phòng và tỷ lệ lấp đầy.
- Doanh thu, tiền đã thu và còn phải thu.
- Đặt phòng cần xử lý.
- Lịch ca và nhân viên.
- Lượt sử dụng, doanh thu dịch vụ và dịch vụ tạm ngưng.

### Lễ tân

- Đặt phòng chờ xác nhận, khách sắp đến, yêu cầu hủy và hóa đơn còn nợ.
- Danh sách check-in/check-out trong ngày.
- Tình trạng phòng.
- Tra cứu nhanh theo mã đặt phòng, tên khách, số điện thoại hoặc số phòng.

### Khách hàng

- Đặt phòng sắp tới và trạng thái.
- Lịch sử lưu trú/đặt phòng.
- Hóa đơn, số đã thanh toán và số còn phải trả.
- Tìm phòng, tạo đặt phòng, gửi yêu cầu hủy và cập nhật hồ sơ.

Mỗi KPI cần có công thức rõ ràng; số liệu phải tôn trọng phạm vi chi nhánh và không cộng trùng hóa đơn/chi tiết hóa đơn.

## 9. Ứng dụng và màn hình nên xây dựng

Đây là định hướng triển khai dựa trên các nghiệp vụ trong đặc tả, không phải những ứng dụng đã có sẵn trong repository.

### 9.1. Website khách hàng

- Đăng ký, đăng nhập và quản lý hồ sơ.
- Tìm kiếm chi nhánh/phòng theo ngày và số người.
- Xem chi tiết phòng, tiện nghi, giá và chính sách.
- Đặt phòng, theo dõi trạng thái và gửi yêu cầu hủy.
- Xem lịch sử lưu trú, hóa đơn và thanh toán.

### 9.2. Trang quản trị nội bộ

- Dashboard Admin và dashboard chi nhánh.
- Quản lý chi nhánh, loại phòng, phòng và bảng giá.
- Quản lý nhân viên, ca làm và phân ca.
- Quản lý dịch vụ theo chi nhánh.
- Xử lý đặt phòng, check-in/check-out.
- Lập hóa đơn, ghi nhận thanh toán và xem báo cáo.
- Quản lý tài khoản, vai trò, quyền và nhật ký.

### 9.3. Màn hình vận hành cho lễ tân

Nên ưu tiên giao diện lịch phòng theo ngày/tuần, danh sách khách đến/trả trong ngày, tìm kiếm nhanh và các thao tác xác nhận, check-in, check-out. Đây là khu vực được sử dụng thường xuyên trong vận hành.

### 9.4. Các tiện ích có thể phát triển sau

- Xuất hóa đơn PDF.
- Gửi email/thông báo khi đặt phòng được xác nhận hoặc thay đổi.
- Thanh toán trực tuyến qua cổng thanh toán.
- Mã QR cho vé điện tử hoặc tra cứu đặt phòng.
- Giao diện tối ưu cho điện thoại để nhân viên cập nhật dịch vụ/lịch làm.
- Báo cáo nâng cao và phân tích xu hướng doanh thu/công suất.

Các tiện ích trên cần được xếp vào giai đoạn sau, sau khi quy trình đặt phòng, lưu trú và thanh toán cốt lõi hoạt động ổn định.

## 10. Gợi ý nhóm API

Các endpoint dưới đây lấy theo định hướng trong đặc tả; tên và cấu trúc có thể điều chỉnh khi thiết kế backend.

| Nhóm | Endpoint ví dụ |
|---|---|
| Xác thực | `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/me` |
| Chi nhánh | `GET/POST /api/branches`, `GET/PUT /api/branches/{id}` |
| Phòng/giá | `GET/POST /api/rooms`, `GET/POST /api/room-types`, `GET/POST /api/prices` |
| Đặt phòng | `GET /api/availability`, `POST /api/bookings`, `GET /api/bookings/{id}`, `PATCH /api/bookings/{id}/confirm` |
| Lưu trú | `POST /api/bookings/{id}/check-in`, `POST /api/bookings/{id}/check-out` |
| Dịch vụ | `GET/POST /api/services`, `POST /api/service-usages` |
| Nhân sự | `GET/POST /api/employees`, `GET/POST /api/shifts`, `POST /api/shift-assignments` |
| Hóa đơn | `POST /api/invoices`, `GET /api/invoices/{id}`, `POST /api/invoices/{id}/payments` |
| Dashboard | `GET /api/dashboard/admin`, `GET /api/dashboard/branch`, `GET /api/dashboard/front-desk` |

Khi triển khai cần thống nhất response, phân trang, validate, mã lỗi, xác thực và phân quyền.

## 11. Yêu cầu phi chức năng

- Băm mật khẩu bằng thuật toán phù hợp; không lưu mật khẩu thuần.
- Kiểm tra quyền ở backend và kiểm tra phạm vi chi nhánh.
- Dùng `DECIMAL` cho tiền tệ, không dùng `FLOAT`/`DOUBLE`.
- Các thao tác quan trọng phải có transaction và nhật ký.
- Danh sách lớn cần phân trang, tìm kiếm, lọc và sắp xếp.
- Dashboard cần giới hạn khoảng thời gian truy vấn; cân nhắc cache/bảng tổng hợp khi dữ liệu lớn.
- Thống nhất cách lưu ngày giờ và hiển thị theo múi giờ `Asia/Ho_Chi_Minh`.
- Có quy trình sao lưu và phục hồi dữ liệu.

## 12. Lộ trình triển khai đề xuất

1. **Chốt nghiệp vụ và ERD:** làm rõ đặt phòng nhiều phòng, hóa đơn và nhiều lần thanh toán, quan hệ tài khoản với khách hàng/nhân viên.
2. **Rà soát schema:** giải quyết các điểm còn mở, đặc biệt lịch bảo trì, giá theo mùa và quan hệ hóa đơn.
3. **Xây dựng xác thực và phân quyền:** đăng ký/đăng nhập, hồ sơ, role, quyền và phạm vi chi nhánh.
4. **Xây dựng danh mục:** chi nhánh, loại phòng, phòng, bảng giá và dịch vụ.
5. **Xây dựng đặt phòng:** tìm phòng, kiểm tra khả dụng, tạo, xác nhận, hủy và giữ phòng.
6. **Xây dựng vận hành lưu trú:** check-in, ghi nhận dịch vụ, check-out.
7. **Xây dựng tài chính:** hóa đơn, chi tiết, thanh toán, công nợ và xuất PDF.
8. **Xây dựng nhân sự và báo cáo:** ca làm, phân ca, dashboard theo vai trò.
9. **Kiểm thử:** đặt trùng lịch, đặt đồng thời, đổi giá, hủy, hoàn tiền, thanh toán nhiều lần và truy cập sai chi nhánh.

## 13. Các quyết định cần chốt trước khi code

- Một đặt phòng có thể đặt nhiều phòng không? Schema hiện tại đã hỗ trợ chi tiết nhiều phòng.
- Một đặt phòng có thể có nhiều hóa đơn không? Schema hiện tại đang giới hạn một hóa đơn trên một đặt phòng.
- Khách có bắt buộc đăng nhập để đặt phòng không?
- Giữ phòng chờ xác nhận trong bao lâu và khi hết hạn có tự giải phóng không?
- Tiền cọc tính theo tỷ lệ nào và trên cơ sở nào?
- Giá được tính theo mùa, từng ngày, cuối tuần hay ngày lễ?
- Có hỗ trợ check-in sớm/check-out muộn và phụ thu không?
- Trạng thái “Trống” và “Đã sẵn sàng” khác nhau như thế nào?
- Ai được xác nhận/hủy đặt phòng, điều chỉnh hóa đơn và hoàn tiền?

## 14. Phạm vi phiên bản đầu tiên nên hoàn thành

Để tránh làm quá rộng ngay từ đầu, phiên bản đầu tiên nên tập trung vào:

1. Đăng ký/đăng nhập và phân quyền.
2. Quản lý chi nhánh, loại phòng, phòng và giá.
3. Tra cứu khả dụng và đặt phòng.
4. Xác nhận/hủy đặt phòng.
5. Check-in/check-out.
6. Ghi nhận dịch vụ.
7. Hóa đơn và ghi nhận thanh toán.
8. Dashboard cơ bản cho Admin, quản lý chi nhánh và lễ tân.

Các tính năng như QR, thanh toán trực tuyến, thông báo tự động và phân tích nâng cao có thể triển khai sau.

---

## Nguồn và phạm vi tài liệu

- Tài liệu nghiệp vụ: *Đặc tả chức năng và nghiệp vụ – Website quản lý chuỗi khách sạn*, phiên bản 1.0, ngày 12/11/2026.
- Repository: `README.md`, `sql/01_schema.sql`, `sql/02_seed_rbac.sql`, `sql/03_triggers.sql`, `sql/05_import_order.md` và cấu trúc CSV trong `data/csv/`.

Tài liệu này mô tả bài toán, đối chiếu cơ sở dữ liệu và định hướng phát triển. Nó không xác nhận rằng website/API đã được xây dựng hoặc dữ liệu đã nhập thành công trên MySQL.
