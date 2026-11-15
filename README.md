# Hệ thống Quản lý Chuỗi Khách sạn & Khu vui chơi 3 miền (BTL CSDL)

Kho lưu trữ này là đồ án hoàn chỉnh cho bài toán **Quản lý Chuỗi Khách sạn kết hợp Khu vui chơi**, bao gồm Cơ sở dữ liệu MySQL 8 (28 bảng chính quy + 2 bảng mở rộng, Trigger, View, Function, Stored Procedure, RBAC), Backend API (**FastAPI + PyMySQL**), **Trợ lý AI Agent (Pure-CPU Hybrid RAG + Semantic Intent Router)** và Frontend Web App (**React + Vite + Tailwind CSS**).

---

## 1. Kiến trúc & Cấu trúc thư mục

```text
btl_csdl/
├── backend/                        # Backend REST API (FastAPI + PyMySQL)
│   ├── app/
│   │   ├── main.py                 # Khởi tạo FastAPI, CORS, exception handler MySQL & schema migration
│   │   ├── config.py               # Đọc cấu hình MySQL, JWT, CORS, VietQR MB Bank, Webhook & Gemini API từ .env
│   │   ├── db.py                   # Connection pool PyMySQL (LifoQueue) & helper gọi Stored Procedure
│   │   ├── security.py             # Xác thực JWT (bắt buộc & tùy chọn), nạp profile RBAC & kiểm tra quyền chi nhánh
│   │   ├── services/
│   │   │   ├── booking_rules.py    # Logic ngày lễ dương/âm lịch, kiểm tra voucher theo phạm vi, dịch vụ & vé
│   │   │   ├── rag_engine.py       # Pure-CPU Hybrid RAG (BM25 Unigram+Bigram + Char 3-gram RRF) trên tri thức & DB
│   │   │   ├── intent_router.py    # Bộ định tuyến ngữ nghĩa toàn câu TF-IDF Cosine & trích xuất thực thể (ngày/vùng/hạng phòng)
│   │   │   ├── agent_tools.py      # Tập công cụ DB có kiểm soát RBAC (tìm phòng, giá, voucher, BI, read-only SQL)
│   │   │   └── ai_agent.py         # Điều phối Local Hybrid Agent (mặc định, 0 GPU) & Gemini Function-Calling tùy chọn
│   │   └── routers/
│   │       ├── auth.py             # Đăng ký, đăng nhập, xem & cập nhật hồ sơ cá nhân (/api/auth/*)
│   │       ├── catalog.py          # Danh mục chi nhánh, loại phòng, combo, dịch vụ, khu vui chơi, voucher
│   │       ├── bookings.py         # Tìm phòng trống, đặt phòng, kiểm tra ngày lễ, check-in/out, OTP hủy đơn
│   │       ├── operations.py       # Quản lý phòng, đặt dịch vụ đa vai trò, phát hành & quét vé QR, khách walk-in
│   │       ├── finance.py          # Chi tiết hóa đơn, sinh VietQR MB Bank, polling trạng thái, xác nhận thu tiền
│   │       ├── bank_webhook.py     # Giải mã chuỗi EMVCo VietQR & webhook đối soát chuyển khoản tự động
│   │       ├── notifications.py    # Hộp thông báo OTP hủy đơn & xác nhận dịch vụ của khách hàng
│   │       ├── admin.py            # Báo cáo doanh thu, xếp hạng phòng/dịch vụ, ca làm & nhật ký hoạt động
│   │       └── ai_agent.py         # API Trợ lý AI (/api/ai/capabilities, /api/ai/chat)
│   ├── tests/
│   │   └── test_api.py             # Bộ kiểm thử API & AI/RAG tự động bằng pytest + FastAPI TestClient
│   ├── .env.example                # Mẫu biến môi trường kết nối MySQL, ngân hàng & Gemini API (tùy chọn)
│   ├── pytest.ini
│   └── requirements.txt
├── frontend/                       # Giao diện Web React + Vite + Tailwind CSS
│   ├── src/
│   │   ├── App.jsx                 # Khung ứng dụng 4 phân hệ, chuông thông báo polling & gắn Widget Trợ lý AI
│   │   ├── api/client.js           # Helper fetch API (tự đính kèm JWT & xử lý hết phiên 401)
│   │   ├── utils/format.js         # Định dạng tiền tệ VND & ngày/giờ hiển thị
│   │   ├── pages/
│   │   │   ├── BookingPortalPage.jsx   # Đặt phòng, chặn ngày trả không hợp lệ, chọn vé & voucher lễ/thường, nhận prefill từ AI
│   │   │   ├── FrontDeskPage.jsx       # Bàn lễ tân: nhận/trả phòng, hủy kèm OTP, thêm dịch vụ, thu tiền
│   │   │   ├── TicketScannerPage.jsx   # Soát vé QR, chọn dịch vụ/vé cho mọi vai trò, bảng giá chi nhánh
│   │   │   └── AdminDashboardPage.jsx  # Thống kê doanh thu, quản lý ca nhân viên & audit log
│   │   └── components/
│   │       ├── AiAssistantWidget.jsx   # Widget chat AI nổi (hiển thị vai trò/mode, nút điền form đặt phòng, bảng SQL cho Admin)
│   │       ├── Badge.jsx               # Nhãn trạng thái thống nhất
│   │       ├── CancelBookingModal.jsx  # Hộp thoại hủy đơn (2 bước gửi/nhập OTP với Admin & Lễ tân)
│   │       ├── InvoiceModal.jsx        # Chi tiết hóa đơn, giao dịch thanh toán & thu tiền trực tiếp
│   │       ├── LoginModal.jsx          # Đăng nhập & chọn nhanh 5 tài khoản demo
│   │       ├── NotificationModal.jsx   # Hộp thông báo khách hàng (đọc OTP, xác nhận/từ chối dịch vụ)
│   │       ├── PaymentQrModal.jsx      # Hiển thị VietQR MB Bank, đếm ngược/polling trạng thái thanh toán
│   │       └── ProfileModal.jsx        # Xem & chỉnh sửa hồ sơ tài khoản
│   ├── package.json
│   └── vite.config.js              # Dev server cổng 5173 (host: true, allowedHosts: true, proxy /api -> 127.0.0.1:8000)
├── data/csv/
│   ├── *.csv                       # 21 tệp CSV dữ liệu nghiệp vụ mẫu
│   └── phan_quyen/*.csv            # 7 tệp CSV mẫu phân quyền RBAC
├── sql/
│   ├── 01_schema.sql               # Tạo DB quan_ly_khach_san, 21 bảng nghiệp vụ + 7 bảng RBAC
│   ├── 02_seed_rbac.sql            # Khởi tạo 5 vai trò, tập quyền & gán quyền
│   ├── 03_triggers.sql             # Trigger chống đặt trùng lịch phòng & đồng bộ tổng hóa đơn
│   ├── 04_data_audit.sql           # Kiểm tra tính hợp lệ dữ liệu sau khi nạp CSV
│   ├── 05_import_order.md          # Thứ tự chuẩn nhập 21 tệp CSV
│   ├── 06_import_csv.sql           # Tập lệnh LOAD DATA LOCAL INFILE nạp 21 tệp CSV nghiệp vụ
│   ├── 07_views_and_procedures.sql # 5 VIEW báo cáo, FUNCTION giá phòng & 4 Stored Procedure giao dịch
│   ├── 08_queries_demo_and_tests.sql # 10 truy vấn báo cáo CTE/Window & kịch bản kiểm thử SQL
│   ├── 09_seed_demo_accounts.sql   # Tạo 5 tài khoản demo & phân công chi nhánh
│   ├── 10_lunar_holiday_pricing.sql# Bảng QUY_DOI_LE_AM_LICH (2024–2028) & hàm tính giá từng đêm
│   ├── 11_operations_procedures.sql# 6 Stored Procedure vận hành (check-in/out, hủy, dịch vụ, voucher, soát vé)
│   └── 12_notifications_and_voucher_scope.sql # Mở rộng MA_GIAM_GIA.LoaiApDung & bảng THONG_BAO_KHACH_HANG
├── docs/
│   ├── PHAN_TICH_BAI_TOAN_VA_DINH_HUONG_PHAT_TRIEN.md
│   └── ERD_VA_MO_HINH_DU_LIEU.md
└── scripts/
    ├── setup_db.ps1                # Script PowerShell cài đặt sạch toàn bộ MySQL DB bằng 1 lệnh
    └── start_dev.ps1               # Script mở nhanh cả Backend (8000) & Frontend (5173)
```

---

## 2. Những gì dự án đã hoàn thiện

### 2.1. Tầng Cơ sở dữ liệu (MySQL 8.0+ / InnoDB)
- **28 bảng chính quy + 2 bảng mở rộng**:
  - 21 bảng nghiệp vụ khách sạn (10 chi nhánh 3 miền), khu vui chơi, hóa đơn, giao dịch thanh toán, voucher, nhân sự & ca làm.
  - 7 bảng RBAC: `TAI_KHOAN`, `VAI_TRO`, `QUYEN`, `TAIKHOAN_VAITRO`, `VAITRO_QUYEN`, `PHAN_CONG_CHI_NHANH`, `NHAT_KY_HOAT_DONG`.
  - Bổ sung `QUY_DOI_LE_AM_LICH` (quy đổi Tết Nguyên Đán & Giỗ Tổ Hùng Vương giai đoạn 2024–2028) và `THONG_BAO_KHACH_HANG` (lưu OTP hủy đơn và đề xuất dịch vụ chờ khách xác nhận).
- **Toàn vẹn dữ liệu ở tầng DB**:
  - Trigger chặn trùng lịch phòng (`trg_ctdp_no_overlap_insert`, `trg_ctdp_no_overlap_update`, `trg_datphong_confirm_no_overlap`) khi đơn ở trạng thái `Đã xác nhận` hoặc `Đang lưu trú`.
  - Trigger tự đồng bộ `HOA_DON.TongTien = SUM(SoLuong * DonGia)` từ `CT_HOA_DON`.
  - Ràng buộc `UNIQUE(CongThanhToan, MaGiaoDichCong)` trên `GIAO_DICH_THANH_TOAN` đảm bảo thanh toán webhook và voucher không bao giờ bị cộng trùng (idempotent).
  - Các Stored Procedure đều bọc `START TRANSACTION` + `FOR UPDATE` + `SIGNAL SQLSTATE '45000'` và ghi nhận `NHAT_KY_HOAT_DONG`.

### 2.2. Các luồng nghiệp vụ Web, API & AI đã triển khai
1. **Đặt phòng & Ràng buộc ngày hợp lệ**:
   - Lọc phòng trống theo chi nhánh, sức chứa, khoảng ngày; tự động tính tổng tiền từng đêm qua `fn_tinh_tien_phong_khoang_ngay` (có xét mùa du lịch & ngày lễ dương/âm lịch).
   - Khi đổi ngày nhận phòng, ngày trả phòng tự xóa để tránh nhầm lịch; các ngày trước hoặc bằng ngày nhận phòng bị vô hiệu hóa không cho chọn (`min` + chặn nhập tay không hợp lệ).
   - Hỗ trợ chọn kèm gói Combo, **đặt kèm vé khu vui chơi** cùng chi nhánh, tìm khách có sẵn hoặc tạo nhanh khách hàng walk-in tại quầy.
2. **Quy tắc tự chọn Voucher theo Ngày thường / Ngày lễ & Phạm vi áp dụng**:
   - Phân loại voucher trong `MA_GIAM_GIA` qua cột `LoaiApDung` (`Khách sạn` / `Khu vui chơi`).
   - **Ngày thường**: khách được chọn tối đa **2 voucher** (tối đa 1 `Khách sạn` + 1 `Khu vui chơi` nếu đặt cả phòng và vé; nếu chỉ đặt phòng chỉ chọn tối đa 1 `Khách sạn`; nếu chỉ đặt vé chỉ chọn tối đa 1 `Khu vui chơi`).
   - **Ngày lễ**: nếu chỉ đặt phòng khách sạn thì **không áp dụng voucher** (0 mã); nếu đặt phòng kèm vé khu vui chơi được chọn **1 trong 2** (tối đa 1 mã); nếu chỉ đặt vé khu vui chơi được chọn tối đa 1 mã `Khu vui chơi`.
3. **Thanh toán chuyển khoản VietQR MB Bank & Webhook tự động**:
   - Khi tạo đơn đặt phòng, mua vé hoặc đặt dịch vụ trực tiếp, hệ thống sinh thông tin VietQR chuẩn Napas 24/7 (`MB Bank` - BIN `970422`, STK `0383356237`, chủ TK `VU NAM KHANH`) kèm nội dung thanh toán chuẩn theo `MaHD`.
   - Giao diện `PaymentQrModal` tự động polling `GET /api/invoices/{ma_hd}/payment-status`, hỗ trợ chọn chế độ thanh toán toàn bộ (100%) hoặc đặt cọc tối thiểu 30%, đồng thời cung cấp endpoint `POST /api/bank/decode-qr` và `POST /api/bank/webhook` (xác thực header `X-Bank-Api-Key`) để tự động hạch toán và chuyển đơn từ `Chờ xác nhận` sang `Đã xác nhận` ngay khi nhận đủ tiền.
4. **Admin/Lễ tân hủy đặt phòng phải xác thực OTP từ máy khách**:
   - Khách hàng tự hủy đơn (`BOOKING.CANCEL_SELF`) được hủy trực tiếp khi đơn chưa check-in.
   - Khi **Admin hoặc Lễ tân** bấm hủy đơn trên hệ thống: bắt buộc bấm **Gửi OTP về máy khách** (`POST /api/bookings/{ma_dp}/cancel-otp`) để phát sinh mã OTP 6 số (hiệu lực 10 phút) gửi vào chuông **Thông báo** trên tài khoản khách hàng (API không trả mã OTP về phía nhân viên). Nhân viên nhập đúng OTP khách cung cấp để hoàn tất hủy đơn.
5. **Đặt Dịch vụ & Vé điện tử QR cho mọi vai trò**:
   - Tại phân hệ **Soát vé QR & Dịch vụ**, tất cả vai trò đã đăng nhập đều có thể chọn đặt **Vé vui chơi QR** và **Dịch vụ chi nhánh** (hoặc bấm **Chọn / Đặt ngay** trực tiếp trên thẻ Bảng giá dịch vụ).
   - **Khách hàng** tự đặt → ghi nhận vào hóa đơn của đơn đang chọn và mở ngay hộp thoại **VietQR** để thanh toán.
   - **Các vai trò nhân viên/quản trị** (Admin, Quản lý, Lễ tân, NV dịch vụ) đặt hộ → gửi thông báo `SERVICE_CONFIRM` về tài khoản khách hàng; chỉ ghi nhận vào hóa đơn và mở QR thanh toán khi khách bấm **Xác nhận & Thanh toán QR**.
6. **Trợ lý AI Aurelia — Pure-CPU Hybrid RAG, Semantic Intent Router & RBAC Tools**:
   - **Kiến trúc thuần CPU (không cần GPU/CUDA)**: Chạy mặc định ở chế độ `local_hybrid_rag`, hoặc tự động nâng cấp lên `gemini_rag_agent` (Function-Calling + RAG) nếu điền `GEMINI_API_KEY` trong `backend/.env`.
   - **Semantic Intent Router** ([`intent_router.py`](backend/app/services/intent_router.py)): Phân loại đa ý định toàn câu bằng TF-IDF Cosine (unigram + word bigram + token phân biệt dấu + char 3-gram), trích xuất ngày tự nhiên/ngày lễ, vùng miền (Bắc/Trung/Nam), chi nhánh, sức chứa, hạng phòng và từ chối lịch sự các câu hỏi ngoài phạm vi.
   - **Hybrid RAG** ([`rag_engine.py`](backend/app/services/rag_engine.py)): Truy xuất tri thức chính sách nghiệp vụ (thanh toán, hoàn cọc/OTP, đổi lịch, thủ tục nhận phòng/CCCD, hóa đơn/VAT, quy tắc & xử lý lỗi voucher, danh bạ 10 chi nhánh 3 miền, bảng giá theo ngày) kết hợp dữ liệu MySQL qua BM25 + Character 3-gram RRF.
   - **Phân quyền 3 chế độ ở backend (`GET /api/ai/capabilities`, `POST /api/ai/chat`)**:
     - `public_concierge` (Khách vãng lai) & `customer_concierge` (Khách hàng): Tìm phòng trống (hiển thị giá `/đêm` & tổng kỳ + nút điền form đặt phòng), so sánh giá phòng giữa các chi nhánh, tư vấn voucher theo ngày lễ/thường, xem khu vui chơi/dịch vụ, giải đáp quy định; khách đăng nhập xem được booking & thông báo OTP cá nhân; bị chặn truy cập BI/SQL nội bộ.
     - `ops_bi_analyst` (Nhân viên/Quản lý/Admin): Tra cứu báo cáo BI doanh thu & công suất lấp đầy giới hạn theo chi nhánh được phân công; riêng **Admin** được chạy truy vấn SQL chỉ đọc an toàn (`SELECT`/`WITH`, chặn bảng nhạy cảm và mọi lệnh ghi).
7. **Phân quyền RBAC & Tài khoản Demo kiểm thử** (mật khẩu chung: `Demo@123456`):

| Tên đăng nhập | Vai trò (`VAI_TRO`) | Phạm vi quyền tiêu biểu |
|---|---|---|
| `admin_hethong` | `ADMIN` | Toàn hệ thống (tất cả 10 chi nhánh), báo cáo, audit log, ca làm, vận hành & AI SQL |
| `quanly_cn1` | `QUAN_LY_CHI_NHANH` | Quản lý toàn bộ nghiệp vụ, giá dịch vụ & báo cáo BI thuộc Chi nhánh #1 |
| `letan_cn1` | `LE_TAN` | Đặt phòng walk-in, check-in/out, hủy kèm OTP, thu tiền, soát vé tại CN #1 |
| `dichvu_cn2` | `NHAN_VIEN_DICH_VU` | Đề xuất dịch vụ, phát hành & quét mã QR vé khu vui chơi tại CN #2 |
| `khach_an` | `KHACH_HANG` | Tự tìm/đặt phòng, vé, dịch vụ, thanh toán VietQR, nhận OTP/xác nhận, tự hủy |

---

## 3. Yêu cầu môi trường

- **Hệ điều hành**: Windows (khuyến nghị PowerShell 5.1+ / Windows Terminal).
- **MySQL Server**: phiên bản **8.0.16 trở lên** (bắt buộc sử dụng engine InnoDB).
- **Python**: **3.11 trở lên** kèm `pip` (chạy thuần CPU, không yêu cầu GPU/CUDA).
- **Node.js**: **18 trở lên** kèm `npm`.

---

## 4. Hướng dẫn Setup & Chạy dự án từng bước

### Bước 1: Khởi tạo & nạp dữ liệu MySQL

Đảm bảo dịch vụ MySQL 8 đang chạy (mặc định tại `127.0.0.1:3306`), sau đó mở PowerShell tại thư mục gốc `d:\Proj\btl_csdl`:

**Cách A — Chạy tự động bằng script (khuyến nghị):**

```powershell
# Nếu đã lưu login-path trong MySQL (ví dụ tên 'btl'):
.\scripts\setup_db.ps1 -LoginPath btl

# Hoặc nhập trực tiếp mật khẩu root khi được hỏi:
.\scripts\setup_db.ps1 -HostName 127.0.0.1 -User root
```

> Script sẽ tự bật `SET GLOBAL local_infile = 1`, reset sạch database `quan_ly_khach_san` và chạy tuần tự từ `01_schema.sql` đến `12_notifications_and_voucher_scope.sql` cùng `08_queries_demo_and_tests.sql`. Nếu `mysql.exe` nằm ở đường dẫn khác mặc định, truyền thêm `-MysqlExe "D:\path\to\mysql.exe"`.

**Cách B — Chạy thủ công từng file SQL:**
Nếu import thủ công trong MySQL CLI / Workbench, cần chạy đúng thứ tự sau (và bật `--local-infile=1` khi chạy file `06_import_csv.sql`):
1. `sql/01_schema.sql`
2. `sql/06_import_csv.sql` *(hoặc theo hướng dẫn trong `sql/05_import_order.md`)*
3. `sql/02_seed_rbac.sql`
4. `sql/03_triggers.sql`
5. `sql/04_data_audit.sql`
6. `sql/07_views_and_procedures.sql`
7. `sql/09_seed_demo_accounts.sql`
8. `sql/10_lunar_holiday_pricing.sql`
9. `sql/11_operations_procedures.sql`
10. `sql/12_notifications_and_voucher_scope.sql`

---

### Bước 2: Cấu hình & cài đặt Backend (FastAPI)

1. Di chuyển vào thư mục `backend` và tạo tệp `.env` từ mẫu:
   ```powershell
   cd d:\Proj\btl_csdl\backend
   Copy-Item .env.example .env
   ```
2. Mở `backend/.env` và điền thông tin kết nối MySQL của máy bạn (đặc biệt là `MYSQL_PASSWORD`):
   ```env
   MYSQL_HOST=127.0.0.1
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=mat_khau_mysql_cua_ban
   MYSQL_DATABASE=quan_ly_khach_san
   JWT_SECRET=doi-chuoi-bi-mat-it-nhat-32-ky-tu-khi-trien-khai
   JWT_EXPIRE_MINUTES=720
   CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5175,http://127.0.0.1:5175
   BANK_CODE=MB
   BANK_BIN=970422
   BANK_NAME=MB Bank (Ngân hàng Quân đội)
   BANK_ACCOUNT_NO=0383356237
   BANK_ACCOUNT_NAME=VU NAM KHANH
   BANK_WEBHOOK_SECRET=btl-bank-webhook-secret-demo
   # Tùy chọn: để trống sẽ dùng Local Hybrid RAG thuần CPU mặc định
   GEMINI_API_KEY=
   GEMINI_MODEL=gemini-2.5-flash
   ```
3. Cài đặt các thư viện Python:
   ```powershell
   pip install -r requirements.txt
   ```

---

### Bước 3: Cài đặt Frontend (React + Vite)

```powershell
cd d:\Proj\btl_csdl\frontend
npm install
```

---

### Bước 4: Khởi chạy toàn bộ ứng dụng

**Cách A — Mở nhanh cả 2 server bằng 1 lệnh PowerShell:**
```powershell
cd d:\Proj\btl_csdl
.\scripts\start_dev.ps1
```

**Cách B — Chạy thủ công trên 2 cửa sổ terminal riêng:**
- **Terminal 1 (Backend API — cổng `8000`)**:
  ```powershell
  cd d:\Proj\btl_csdl\backend
  uvicorn app.main:app --reload --port 8000
  ```
- **Terminal 2 (Frontend Web — cổng `5173`)**:
  ```powershell
  cd d:\Proj\btl_csdl\frontend
  npm run dev
  ```

Sau khi cả hai khởi động xong:
- Giao diện Web: `http://localhost:5173`
- Tài liệu API Swagger: `http://127.0.0.1:8000/docs`
- Kiểm tra nhanh sức khỏe backend: `http://127.0.0.1:8000/api/health`

*(Lưu ý: `frontend/vite.config.js` đã bật `host: true`, `allowedHosts: true` và proxy `/api/*` sang `http://127.0.0.1:8000`. Nếu muốn chia sẻ bản demo ra ngoài qua Cloudflare Quick Tunnel sau khi đã chạy cả Backend và Frontend, chỉ cần mở thêm 1 terminal chạy `cloudflared tunnel --url http://127.0.0.1:5173`).*

---

## 5. Chạy kiểm thử & Build sản phẩm

### Kiểm thử Backend API & AI/RAG (`pytest`)
Đảm bảo MySQL đang chạy và đã cấu hình `backend/.env`:
```powershell
cd d:\Proj\btl_csdl
pytest backend/tests/test_api.py -v
```
Bộ test tự động kiểm tra đầy đủ 9 nhóm kịch bản: catalog, phân quyền RBAC theo chi nhánh, vòng đời đặt phòng & trigger chống trùng lịch, quét vé QR & ca làm, webhook thanh toán VietQR chống trùng, quy tắc voucher lễ/thường, quy trình Admin hủy đơn bằng OTP khách hàng, đặt dịch vụ & xác nhận thông báo, cùng bộ kiểm thử AI Agent (Semantic Intent Router, Hybrid RAG, chống rò rỉ tài liệu kỹ thuật và RBAC BI/SQL).

### Build Frontend Production (`vite build`)
```powershell
cd d:\Proj\btl_csdl\frontend
npm run build
```

---

## 6. Quy ước dữ liệu & Lưu ý vận hành

- **Định dạng ngày/giờ**: Các cột `DATE` / `DATETIME` lưu chuẩn MySQL (`YYYY-MM-DD`, `YYYY-MM-DD HH:MM:SS`); khi hiển thị lên UI/báo cáo dùng định dạng `dd/MM/yyyy`.
- **Bảng giá `BANG_GIA`**: Hai cột `NgayBD` và `NgayKT` sử dụng kiểu `VARCHAR(80)` vì dữ liệu nguồn chứa cả mốc tháng-ngày (`MM-DD`) lẫn mô tả ngày lễ âm lịch; việc tính giá chính xác từng đêm được xử lý tập trung qua `QUY_DOI_LE_AM_LICH` và `fn_tinh_tien_phong_khoang_ngay`.
- **Tiền tệ**: Toàn bộ giá trị tiền tệ dùng `DECIMAL`, tuyệt đối không dùng `FLOAT`/`DOUBLE` để tránh sai số làm tròn.
- **Tài khoản mẫu**: Toàn bộ dữ liệu khách hàng, nhân viên và giao dịch trong `data/csv/` chỉ phục vụ học tập và kiểm thử.
