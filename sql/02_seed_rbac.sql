USE quan_ly_khach_san;

INSERT INTO VAI_TRO(MaCode,TenVaiTro,MoTa) VALUES
('KHACH_HANG','Khách hàng','Chỉ truy cập hồ sơ, đặt phòng, hóa đơn của chính mình'),
('LE_TAN','Lễ tân','Thao tác nghiệp vụ tại chi nhánh được phân công'),
('NHAN_VIEN_DICH_VU','Nhân viên dịch vụ','Xem ca và ghi nhận dịch vụ tại chi nhánh được phân công'),
('QUAN_LY_CHI_NHANH','Quản lý chi nhánh','Quản lý hoạt động của chi nhánh được giao'),
('ADMIN','Quản trị hệ thống','Quản trị toàn hệ thống');

INSERT INTO QUYEN(MaCode,TenQuyen,NhomQuyen) VALUES
('PROFILE.READ_SELF','Xem hồ sơ của mình','Tài khoản'),
('PROFILE.UPDATE_SELF','Sửa hồ sơ của mình','Tài khoản'),
('BOOKING.CREATE','Tạo đặt phòng','Đặt phòng'),
('BOOKING.READ_SELF','Xem đặt phòng của mình','Đặt phòng'),
('BOOKING.CANCEL_SELF','Gửi yêu cầu hủy đặt phòng của mình','Đặt phòng'),
('BOOKING.READ_BRANCH','Xem đặt phòng trong chi nhánh','Đặt phòng'),
('BOOKING.CONFIRM','Xác nhận đặt phòng','Đặt phòng'),
('BOOKING.CHECKIN_OUT','Check-in/check-out','Đặt phòng'),
('ROOM.READ_BRANCH','Xem phòng chi nhánh','Phòng'),
('ROOM.MANAGE_BRANCH','Quản lý phòng và giá chi nhánh','Phòng'),
('SERVICE.READ_BRANCH','Xem dịch vụ chi nhánh','Dịch vụ'),
('SERVICE.RECORD_USE','Ghi nhận sử dụng dịch vụ','Dịch vụ'),
('SERVICE.MANAGE_BRANCH','Quản lý dịch vụ chi nhánh','Dịch vụ'),
('STAFF.READ_BRANCH','Xem nhân viên và lịch ca','Nhân sự'),
('STAFF.MANAGE_BRANCH','Quản lý nhân viên và phân ca','Nhân sự'),
('INVOICE.READ_SELF','Xem hóa đơn của mình','Tài chính'),
('INVOICE.READ_BRANCH','Xem hóa đơn chi nhánh','Tài chính'),
('INVOICE.MANAGE','Lập và điều chỉnh hóa đơn','Tài chính'),
('REPORT.READ_BRANCH','Xem báo cáo chi nhánh','Báo cáo'),
('SYSTEM.ALL','Toàn quyền quản trị hệ thống','Quản trị');

-- Khach hang
INSERT INTO VAI_TRO_QUYEN
SELECT r.MaVaiTro,p.MaQuyen FROM VAI_TRO r JOIN QUYEN p
WHERE r.MaCode='KHACH_HANG' AND p.MaCode IN
('PROFILE.READ_SELF','PROFILE.UPDATE_SELF','BOOKING.CREATE','BOOKING.READ_SELF','BOOKING.CANCEL_SELF','INVOICE.READ_SELF');

-- Le tan
INSERT INTO VAI_TRO_QUYEN
SELECT r.MaVaiTro,p.MaQuyen FROM VAI_TRO r JOIN QUYEN p
WHERE r.MaCode='LE_TAN' AND p.MaCode IN
('BOOKING.READ_BRANCH','BOOKING.CONFIRM','BOOKING.CHECKIN_OUT','ROOM.READ_BRANCH','SERVICE.READ_BRANCH','SERVICE.RECORD_USE','INVOICE.READ_BRANCH','INVOICE.MANAGE');

-- Nhan vien dich vu
INSERT INTO VAI_TRO_QUYEN
SELECT r.MaVaiTro,p.MaQuyen FROM VAI_TRO r JOIN QUYEN p
WHERE r.MaCode='NHAN_VIEN_DICH_VU' AND p.MaCode IN
('SERVICE.READ_BRANCH','SERVICE.RECORD_USE','STAFF.READ_BRANCH');

-- Quan ly chi nhanh
INSERT INTO VAI_TRO_QUYEN
SELECT r.MaVaiTro,p.MaQuyen FROM VAI_TRO r JOIN QUYEN p
WHERE r.MaCode='QUAN_LY_CHI_NHANH' AND p.MaCode IN
('BOOKING.READ_BRANCH','BOOKING.CONFIRM','BOOKING.CHECKIN_OUT','ROOM.READ_BRANCH','ROOM.MANAGE_BRANCH',
'SERVICE.READ_BRANCH','SERVICE.RECORD_USE','SERVICE.MANAGE_BRANCH','STAFF.READ_BRANCH','STAFF.MANAGE_BRANCH',
'INVOICE.READ_BRANCH','INVOICE.MANAGE','REPORT.READ_BRANCH');

-- Admin: cap quyen tong he thong.
INSERT INTO VAI_TRO_QUYEN
SELECT r.MaVaiTro,p.MaQuyen FROM VAI_TRO r CROSS JOIN QUYEN p WHERE r.MaCode='ADMIN';

-- Phan cong chi nhanh duoc gan sau khi tao tai khoan noi bo.
-- Khong tu dong tao tai khoan/mat khau mac dinh trong du lieu mau.
