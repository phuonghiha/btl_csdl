--Cơ bản: Liệt kê các phòng loại "President" đang ở trạng thái 'Trong' và 'DaSanSang' tại Chi nhánh 1.
--Inner Join: Hiển thị lịch sử sử dụng dịch vụ Spa/Nhà hàng của khách hàng đang ở phòng 302.
--Group By: Tính tổng doanh thu dịch vụ phụ (không tính tiền phòng) theo từng tháng trong năm 2025.
--Having: Tìm các chi nhánh khách sạn có công suất sử dụng phòng trung bình trong tháng 7 đạt trên 85%.
--Outer Join: Hiển thị tất cả danh mục dịch vụ phụ trợ và số lượt khách sử dụng (kể cả dịch vụ chưa có ai sử dụng).
--Correlated Subquery: Tìm những khách hàng có tổng chi tiêu cho 1 lần lưu trú cao hơn mức chi tiêu trung bình của tất cả các khách hàng lưu trú tại cùng loại phòng đó.
--Subquery với IN & ALL: Tìm loại phòng có giá thuê theo ngày cao hơn tất cả các phòng thuộc chi nhánh Đà Nẵng.
--Window Functions: Sử dụng LAG() và LEAD() để tính khoảng cách số ngày giữa 2 lần đặt phòng liên tiếp của từng khách hàng thân thiết.
--
--1--
SELECT
    P.MaPhong,
    P.SoPhong,
    P.Tang,
    LP.TenLP,
    P.TrangThai
FROM PHONG P
JOIN LOAI_PHONG LP
    ON P.MaLP = LP.MaLP
WHERE LP.TenLP = 'Presidential Suite'
  AND P.MaCN = 1
  AND P.TrangThai IN ('Trống', 'Đã sẵn sàng');
--2--
SELECT
    KH.MaKH,
    KH.HoTen,
    P.SoPhong,
    DV.TenDV,
    DV.LoaiDV,
    SDV.ThoiGianSD,
    SDV.SoLuong,
    SDV.DonGiaTaiThoiDiem,
    SDV.SoLuong * SDV.DonGiaTaiThoiDiem AS ThanhTien
FROM KHACH_HANG KH
JOIN DAT_PHONG DP
    ON KH.MaKH = DP.MaKH
JOIN CT_DAT_PHONG CTDP
    ON DP.MaDP = CTDP.MaDP
JOIN PHONG P
    ON CTDP.MaPhong = P.MaPhong
JOIN SU_DUNG_DV SDV
    ON DP.MaDP = SDV.MaDP
JOIN DICH_VU DV
    ON SDV.MaDV = DV.MaDV
WHERE P.SoPhong = '102'
  AND DV.LoaiDV IN ('Spa', 'Nhà hàng')
ORDER BY SDV.ThoiGianSD;

--3--
SELECT
    MONTH(ThoiGianSD) AS Thang,
    SUM(SoLuong * DonGiaTaiThoiDiem) AS TongDoanhThu
FROM SU_DUNG_DV
WHERE ThoiGianSD >= '2025-01-01'
  AND ThoiGianSD < '2026-01-01'
GROUP BY MONTH(ThoiGianSD)
ORDER BY Thang;
--4--
SELECT
    CN.MaCN,
    CN.TenCN,
    ROUND(
        SUM(
            DATEDIFF(
                LEAST(CTDP.NgayCheckOut, '2025-08-01'),
                GREATEST(CTDP.NgayCheckIn, '2025-07-01')
            )
        ) * 100.0 / (COUNT(DISTINCT P.MaPhong) * 31),
        2
    ) AS CongSuatSuDung
FROM CHI_NHANH CN
JOIN PHONG P
    ON CN.MaCN = P.MaCN
LEFT JOIN CT_DAT_PHONG CTDP
    ON P.MaPhong = CTDP.MaPhong
    AND CTDP.NgayCheckIn < '2025-08-01'
    AND CTDP.NgayCheckOut > '2025-07-01'
GROUP BY CN.MaCN, CN.TenCN
HAVING CongSuatSuDung > 85
ORDER BY CongSuatSuDung DESC;
--5--
SELECT
    DV.MaDV,
    DV.TenDV,
    DV.LoaiDV,
    COUNT(SDV.MaSD) AS SoLuotSuDung
FROM DICH_VU DV
LEFT JOIN SU_DUNG_DV SDV
    ON DV.MaDV = SDV.MaDV
GROUP BY
    DV.MaDV,
    DV.TenDV,
    DV.LoaiDV
ORDER BY SoLuotSuDung DESC;
--6--
WITH CHI_TIEU AS (
    SELECT
        KH.MaKH,
        KH.HoTen,
        DP.MaDP,
        LP.MaLP,
        LP.TenLP,
        HD.TongTien
    FROM KHACH_HANG KH
    JOIN DAT_PHONG DP
        ON KH.MaKH = DP.MaKH
    JOIN CT_DAT_PHONG CTDP
        ON DP.MaDP = CTDP.MaDP
    JOIN PHONG P
        ON CTDP.MaPhong = P.MaPhong
    JOIN LOAI_PHONG LP
        ON P.MaLP = LP.MaLP
    JOIN HOA_DON HD
        ON DP.MaDP = HD.MaDP
    GROUP BY
        KH.MaKH,
        KH.HoTen,
        DP.MaDP,
        LP.MaLP,
        LP.TenLP,
        HD.TongTien
)

SELECT
    CT.MaKH,
    CT.HoTen,
    CT.MaDP,
    CT.TenLP,
    CT.TongTien AS TongChiTieu
FROM CHI_TIEU CT
WHERE CT.TongTien > (
    SELECT AVG(CT2.TongTien)
    FROM CHI_TIEU CT2
    WHERE CT2.MaLP = CT.MaLP
)
ORDER BY CT.TongTien DESC;
--7--
SELECT DISTINCT
    LP.MaLP,
    LP.TenLP,
    BG.GiaPhong
FROM LOAI_PHONG LP
JOIN BANG_GIA BG ON LP.MaLP = BG.MaLP
WHERE BG.GiaPhong > ALL (
    SELECT BG2.GiaPhong
    FROM BANG_GIA BG2
    WHERE BG2.MaLP IN (
        SELECT DISTINCT P.MaLP
        FROM PHONG P
        JOIN CHI_NHANH CN ON P.MaCN = CN.MaCN
        WHERE CN.TenCN LIKE '%Đà Nẵng%'
    )
)
ORDER BY BG.GiaPhong DESC;
--8--
WITH KH_THAN_THIET AS (
    SELECT MaKH
    FROM DAT_PHONG
    GROUP BY MaKH
    HAVING COUNT(MaDP) >= 2
),
LICH_SU_DAT_PHONG AS (
    SELECT
        KH.MaKH,
        KH.HoTen,
        DP.MaDP,
        DP.NgayDat,

        LAG(DP.NgayDat) OVER (
            PARTITION BY KH.MaKH
            ORDER BY DP.NgayDat, DP.MaDP
        ) AS NgayDatTruoc,

        LEAD(DP.NgayDat) OVER (
            PARTITION BY KH.MaKH
            ORDER BY DP.NgayDat, DP.MaDP
        ) AS NgayDatTiepTheo

    FROM KHACH_HANG KH
    JOIN DAT_PHONG DP ON KH.MaKH = DP.MaKH
    WHERE KH.MaKH IN (
        SELECT MaKH
        FROM KH_THAN_THIET
    )
)
SELECT
    MaKH,
    HoTen,
    MaDP,
    NgayDat,
    NgayDatTruoc,
    CASE
        WHEN NgayDatTruoc IS NOT NULL
        THEN DATEDIFF(NgayDat, NgayDatTruoc)
        ELSE NULL
    END AS SoNgayTuLanTruoc,

    NgayDatTiepTheo,
    CASE
        WHEN NgayDatTiepTheo IS NOT NULL
        THEN DATEDIFF(NgayDatTiepTheo, NgayDat)
        ELSE NULL
    END AS SoNgayDenLanTiepTheo

FROM LICH_SU_DAT_PHONG
ORDER BY MaKH, NgayDat, MaDP;