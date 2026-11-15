import math
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

from ..db import fetch_all

_INDEX_CACHE: dict[str, Any] = {
    "built_at": 0.0,
    "docs": [],
    "idf": {},
    "doc_tf": [],
    "doc_len": [],
    "avgdl": 1.0,
    "ngram_vecs": [],
}
_CACHE_TTL_SECONDS = 300.0
_BM25_K1 = 1.5
_BM25_B = 0.75
_RRF_K = 60.0

_STOP_WORDS = {
    "va", "la", "cua", "cho", "co", "khong", "duoc", "trong", "nhung", "cac", "nay",
    "khi", "voi", "tai", "den", "tu", "theo", "hay", "nhu", "the", "nao", "gi", "bao",
    "nhieu", "thi", "ma", "de", "ban", "minh", "toi", "he", "thong", "nhe", "a",
    "tung", "moi", "vay", "sao", "neu", "thi", "hoac", "nhung", "and", "for", "with",
    "from", "this", "that", "are", "how", "can", "could", "would",
}

# Domain synonym & paraphrase expansion (pure CPU, covers general resort & ops vocabulary)
_DOMAIN_SYNONYMS: tuple[tuple[str, str], ...] = (
    ("dat nhat", "cao nhat vip sang nhat hang cao presidential"),
    ("dat tien", "cao nhat gia cao vip presidential"),
    ("re nhat", "thap nhat tiet kiem binh dan standard"),
    ("bo dat", "huy phong huy don hoan phong"),
    ("huy don", "huy phong otp xac nhan hoan tien phi huy hoan coc"),
    ("huy phong", "huy don hoan tien phi huy coc otp xac nhan"),
    ("huy lich", "huy phong huy don otp xac nhan hoan tien"),
    ("hoan tien", "hoan coc huy phong phi huy doi soat"),
    ("hoan coc", "hoan tien huy phong phi huy doi soat"),
    ("phi huy", "huy phong hoan tien hoan coc truoc nhan phong"),
    ("coc", "dat coc 30% thanh toan vietqr chuyen khoan"),
    ("tra truoc", "dat coc 30% thanh toan 100% vietqr chuyen khoan"),
    ("tien mat", "thanh toan truc tiep tai quay le tan the ngan hang vietqr"),
    ("thanh toan", "tien mat the ngan hang vietqr chuyen khoan dat coc hoa don"),
    ("phuong thuc", "thanh toan tien mat the ngan hang vietqr chuyen khoan"),
    ("chuyen khoan", "vietqr mb bank thanh toan coc doi soat"),
    ("qr", "vietqr ve dien tu quet ma soat ve"),
    ("doi ngay", "thay doi ngay chinh sua lich nhan phong tra phong huy dat lai"),
    ("thay doi ngay", "doi ngay chinh sua lich nhan phong tra phong huy dat lai"),
    ("doi lich", "doi ngay thay doi ngay chinh sua dat phong huy dat lai"),
    ("chinh sua", "doi ngay thay doi lich dat phong"),
    ("sua ngay", "doi ngay thay doi ngay chinh sua dat phong"),
    ("nhan phong", "check in giay to cccd ho chieu som muon le tan"),
    ("tra phong", "check out muon le tan hoa don"),
    ("check in", "nhan phong luu tru cccd giay to som"),
    ("checkin", "nhan phong luu tru cccd giay to som"),
    ("check out", "tra phong hoa don muon"),
    ("checkout", "tra phong hoa don muon"),
    ("cccd", "giay to tuy than can cuoc ho chieu dang ky nhan phong"),
    ("giay to", "cccd can cuoc ho chieu nhan phong"),
    ("tre em", "suc chua phong gia dinh ve tre em chieu cao 100cm 140cm"),
    ("nguoi lon", "suc chua ve nguoi lon chieu cao 140cm"),
    ("cao tuoi", "ve cao tuoi 60 tuoi"),
    ("voucher", "ma giam gia khuyen mai uu dai"),
    ("ma giam", "voucher khuyen mai uu dai"),
    ("uu dai", "voucher ma giam gia khuyen mai"),
    ("khuyen mai", "voucher ma giam gia uu dai"),
    ("ap dung ma", "tick chon voucher bieu mau dat phong vietqr"),
    ("nhap ma", "tick chon voucher bieu mau dat phong loi khong hop le"),
    ("khong hop le", "loi voucher het han het luot don toi thieu sai pham vi"),
    ("het han", "loi voucher khong hop le ngay ket thuc het luot"),
    ("bao loi", "loi voucher khong hop le ho tro le tan"),
    ("nhieu phong", "2 phong hai phong hoa don ap dung voucher"),
    ("2 phong", "nhieu phong hai phong hoa don ap dung voucher"),
    ("hai phong", "nhieu phong 2 phong hoa don ap dung voucher"),
    ("tong chi phi", "hoa don chi tiet thue phi dich vu phu thu bang ke"),
    ("hoa don", "xem hoa don bang ke chi tiet thue phi dich vu phu thu"),
    ("thue", "hoa don chi tiet tong chi phi vat phi dich vu phu thu"),
    ("vat", "hoa don chi tiet thue phi dich vu phu thu"),
    ("phu thu", "hoa don chi tiet ngay le cuoi tuan thue phi dich vu"),
    ("phi dich vu", "hoa don chi tiet thue phu thu minh bach"),
    ("tro choi", "khu vui choi ve loai ve giai tri cong vien"),
    ("vui choi", "khu vui choi ve loai ve cong vien giai tri"),
    ("hang phong", "loai phong standard superior deluxe family suite presidential suc chua toi da"),
    ("suc chua", "hang phong loai phong standard superior deluxe family suite toi da khach"),
    ("ve cong", "loai ve khu vui choi gia ve qr soat ve"),
    ("soat ve", "ve qr dien tu cong khu vui choi"),
    ("ngay le", "le am lich le duong lich tet gio to 30/4 2/9 phu thu"),
    ("an uong", "dich vu nha hang buffet spa"),
    ("spa", "dich vu thu gian massage xong hoi"),
    ("chi nhanh", "ha noi da nang phu quoc nha trang da lat hoi an sa pa ha long hue tp hcm mien bac mien trung mien nam"),
    ("mien bac", "ha noi sa pa ha long chi nhanh"),
    ("mien trung", "da nang hoi an hue nha trang chi nhanh"),
    ("mien nam", "tp hcm phu quoc da lat chi nhanh"),
)

_REGION_MAP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Miền Bắc", ("ha noi", "sa pa", "sapa", "ha long", "quang ninh", "lao cai")),
    ("Miền Trung", ("da nang", "hoi an", "quang nam", "hue", "thua thien hue", "nha trang", "khanh hoa")),
    ("Miền Nam", ("tp.hcm", "ho chi minh", "sai gon", "phu quoc", "kien giang", "da lat", "lam dong")),
)


@dataclass
class RagChunk:
    chunk_id: str
    source: str
    title: str
    content: str
    category: str
    audience: str = "customer"  # "customer" | "ops"
    ma_cn: int | None = None


def strip_accents(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfkd if unicodedata.category(ch) != "Mn")


def expand_domain_query(query: str) -> str:
    """Append domain-specific synonyms (pure CPU/rule-based) to improve recall."""
    norm = strip_accents(query.lower())
    extras: list[str] = []
    for trigger, expansion in _DOMAIN_SYNONYMS:
        if trigger in norm:
            extras.append(expansion)
    if not extras:
        return query
    return f"{query} {' '.join(extras)}"


def tokenize(text: str) -> list[str]:
    """Extract unigrams (folded + accented distinctions) and folded word bigrams."""
    lowered = text.lower()
    raw_tokens = re.findall(r"[0-9a-zà-ỹ]+", lowered)
    tokens: list[str] = []
    folded_seq: list[str] = []
    for tok in raw_tokens:
        if len(tok) <= 1 and not tok.isdigit():
            continue
        folded = strip_accents(tok)
        if folded in _STOP_WORDS:
            continue
        tokens.append(folded)
        folded_seq.append(folded)
        if tok != folded:
            # Prefix with ac: so accented words (vé vs về, bị vs bi) boost exact sense
            tokens.append(f"ac:{tok}")
    for i in range(len(folded_seq) - 1):
        tokens.append(f"{folded_seq[i]}_{folded_seq[i + 1]}")
    return tokens


def _char_ngrams(text: str, n: int = 3) -> dict[str, float]:
    cleaned = re.sub(r"[^0-9a-z]+", " ", strip_accents(text.lower())).strip()
    if len(cleaned) < n:
        return {cleaned: 1.0} if cleaned else {}
    tf: dict[str, int] = {}
    for i in range(len(cleaned) - n + 1):
        gram = cleaned[i : i + n]
        if gram.strip():
            tf[gram] = tf.get(gram, 0) + 1
    norm = math.sqrt(sum(c * c for c in tf.values())) or 1.0
    return {g: c / norm for g, c in tf.items()}


def _classify_region(branch_text: str) -> str:
    norm = strip_accents(branch_text.lower())
    for region, kws in _REGION_MAP:
        if any(k in norm for k in kws):
            return region
    return "Toàn quốc"


def _curated_policy_chunks() -> list[RagChunk]:
    """Atomic, human-friendly policy chunks covering every system workflow (zero code/SQL/paths)."""
    return [
        RagChunk(
            chunk_id="policy:payment_methods",
            source="Chính sách thanh toán",
            title="Các phương thức thanh toán được hỗ trợ (Tiền mặt, Thẻ & VietQR)",
            content=(
                "- **Tại quầy lễ tân chi nhánh**: Khách hàng có thể thanh toán trực tiếp bằng **Tiền mặt**, **Thẻ ngân hàng**, hoặc **Chuyển khoản / VietQR** khi nhận phòng hoặc trả phòng.\n"
                "- **Khi đặt phòng trực tuyến trên website**: Hệ thống tạo mã **VietQR MB Bank** để chuyển khoản nhanh (hỗ trợ chọn **Đặt cọc tối thiểu 30%** hoặc **Thanh toán toàn bộ 100%**). Hệ thống tự động đối soát nội dung chuyển khoản và cập nhật đơn sang *Đã xác nhận* ngay khi nhận tiền."
            ),
            category="payment",
            audience="customer",
        ),
        RagChunk(
            chunk_id="policy:cancel_and_refund",
            source="Chính sách hủy phòng & hoàn tiền",
            title="Quy định hủy đặt phòng, phí hủy, hoàn cọc và xác thực OTP",
            content=(
                "- **Điều kiện & phí hủy**: Khách được hủy đơn khi đang ở trạng thái *Chờ xác nhận* hoặc *Đã xác nhận* (trước khi nhận phòng). Hệ thống **không thu phí phạt hủy tự động** trước thời điểm nhận phòng.\n"
                "- **Hoàn tiền cọc / đã thanh toán**: Nếu chưa thanh toán hoặc chưa cọc thì hủy không mất phí. Nếu đã chuyển khoản đặt cọc/thanh toán trước, Lễ tân hoặc Quản trị viên chi nhánh sẽ đối soát giao dịch trên hóa đơn để xử lý hoàn tiền hoặc hỗ trợ đổi lịch trực tiếp.\n"
                "- **Thao tác hủy & OTP**: Tự đăng nhập tài khoản để bấm hủy trực tiếp, hoặc yêu cầu Lễ tân hủy giúp — khi hủy qua Lễ tân/Quản trị viên, hệ thống gửi mã **OTP 6 chữ số** (hiệu lực 10 phút) về chuông Thông báo trên tài khoản khách."
            ),
            category="policy",
            audience="customer",
        ),
        RagChunk(
            chunk_id="policy:modify_booking",
            source="Chính sách thay đổi lịch đặt phòng",
            title="Cách thay đổi ngày nhận phòng và ngày trả phòng sau khi đã đặt",
            content=(
                "- Website hiện **chưa hỗ trợ chỉnh sửa trực tiếp ngày nhận phòng / trả phòng** ngay trên đơn đã tạo thành công.\n"
                "- Để đổi lịch trước khi check-in: quý khách có thể hủy đơn hiện tại trên tài khoản rồi đặt lại theo ngày mới, hoặc liên hệ Lễ tân chi nhánh kiểm tra phòng trống và hỗ trợ dời lịch.\n"
                "- **Chi phí phát sinh**: Không có phí phạt đổi ngày trước khi nhận phòng, nhưng **giá phòng sẽ được tính lại theo bảng giá của khoảng ngày mới** (nếu chuyển sang cuối tuần, mùa cao điểm hoặc ngày lễ có thể phát sinh chênh lệch giá)."
            ),
            category="policy",
            audience="customer",
        ),
        RagChunk(
            chunk_id="policy:checkin_and_id",
            source="Thủ tục nhận & trả phòng",
            title="Thủ tục check-in, check-out, giấy tờ tùy thân và yêu cầu nhận sớm / trả muộn",
            content=(
                "- **Giấy tờ cần thiết**: Khi đăng ký tài khoản hoặc làm thủ tục nhận phòng trực tiếp (kể cả khách walk-in), quý khách cần cung cấp **CCCD/CMND** (hoặc giấy tờ tùy thân hợp lệ) cùng số điện thoại liên hệ.\n"
                "- **Nhận phòng sớm / trả phòng muộn**: Tùy thuộc tình trạng phòng trống thực tế trong ngày tại chi nhánh. Quý khách vui lòng gọi trực tiếp số điện thoại chi nhánh hoặc trao đổi với Lễ tân để được kiểm tra và sắp xếp trước.\n"
                "- **Sức chứa phòng**: Mỗi hạng phòng có sức chứa tiêu chuẩn (từ 2 đến 4 khách). Nếu đi đông người hoặc có trẻ em đi cùng, hệ thống ưu tiên gợi ý hạng *Family*, *Suite* hoặc đặt phòng phù hợp với tổng số khách."
            ),
            category="policy",
            audience="customer",
        ),
        RagChunk(
            chunk_id="policy:invoice_and_taxes",
            source="Minh bạch hóa đơn & Chi phí",
            title="Cách tính tổng chi phí, tiền phòng, dịch vụ, phụ thu và xem chi tiết hóa đơn",
            content=(
                "- **Bảng kê chi tiết**: Trên đơn đặt phòng của mình, quý khách bấm **Xem hóa đơn** để kiểm tra từng dòng chi tiết: tiền phòng theo từng đêm (đã tính mùa du lịch/ngày lễ), gói combo, vé khu vui chơi, các dịch vụ phát sinh tại chi nhánh và số tiền được giảm từ voucher.\n"
                "- **Thuế & phụ thu**: Giá phòng và giá dịch vụ niêm yết là mức thu trực tiếp trên hóa đơn; hệ thống **không cộng ẩn thêm thuế VAT hay phí dịch vụ tách rời** ngoài các khoản hiển thị công khai trong chi tiết hóa đơn."
            ),
            category="pricing",
            audience="customer",
        ),
        RagChunk(
            chunk_id="policy:holiday_and_seasonal_pricing",
            source="Chính sách giá phòng & ngày lễ",
            title="Cách tính giá phòng theo từng đêm, mùa du lịch và lịch ngày lễ",
            content=(
                "- Giá phòng được tính chính xác theo từng đêm lưu trú giữa ngày nhận phòng và ngày trả phòng (ngày trả phòng bắt buộc sau ngày nhận phòng).\n"
                "- Các dịp **lễ Dương lịch** (Tết Dương lịch 01/01, 30/04–01/05, Quốc khánh 02/09) và **lễ Âm lịch** (Tết Nguyên Đán, Giỗ Tổ Hùng Vương 10/3 Âm lịch) áp dụng mức giá riêng theo bảng giá từng hạng phòng."
            ),
            category="pricing_rules",
            audience="customer",
        ),
        RagChunk(
            chunk_id="policy:voucher_howto_and_rules",
            source="Chính sách mã giảm giá (Voucher)",
            title="Cách chọn mã giảm giá khi đặt phòng & quy tắc ngày thường / ngày lễ",
            content=(
                "- **Thao tác áp dụng online**: Trong biểu mẫu **Đặt phòng**, sau khi chọn vé khu vui chơi/combo (nếu cần), quý khách tick chọn trực tiếp mã ưu đãi hợp lệ ở mục **Mã giảm giá (Voucher)** trước khi bấm xác nhận đặt đơn. Tiền giảm được trừ ngay vào hóa đơn trước khi tạo mã VietQR.\n"
                "- **Quy định số lượng mã được chọn**:\n"
                "  + **Ngày thường**: Tối đa **2 mã** (tối đa 1 mã Khách sạn + 1 mã Khu vui chơi nếu đặt cả phòng và vé; chỉ đặt phòng chọn tối đa 1 mã Khách sạn; chỉ đặt vé chọn tối đa 1 mã Khu vui chơi).\n"
                "  + **Ngày lễ (Dương lịch / Âm lịch)**: Chỉ đặt khách sạn **không áp dụng mã** (0 mã); có đặt kèm vé khu vui chơi được chọn **tối đa 1 mã**."
            ),
            category="vouchers",
            audience="customer",
        ),
        RagChunk(
            chunk_id="policy:voucher_multi_room",
            source="Voucher cho đơn nhiều phòng",
            title="Áp dụng mã giảm giá khi đặt 2 phòng hoặc nhiều phòng cùng lúc",
            content=(
                "- Mỗi mã giảm giá được áp dụng **1 lần tính trên tổng giá trị của 1 hóa đơn** (không nhân đôi tách riêng theo từng phòng; tổng hóa đơn cần đạt điều kiện *Đơn hàng tối thiểu* của mã).\n"
                "- Trên cổng web trực tuyến mỗi lượt tạo 1 đơn 1 phòng. Nếu gia đình/nhóm đặt 2 phòng trở lên và muốn gộp chung 1 hóa đơn để áp dụng ưu đãi trên tổng đơn, vui lòng liên hệ Lễ tân chi nhánh hỗ trợ tạo đơn gộp."
            ),
            category="vouchers",
            audience="customer",
        ),
        RagChunk(
            chunk_id="policy:voucher_errors",
            source="Xử lý lỗi mã giảm giá",
            title="Nguyên nhân mã giảm giá báo không hợp lệ hoặc hết hạn & cách hỗ trợ",
            content=(
                "- **Các nguyên nhân thường gặp khiến mã không hợp lệ**:\n"
                "  1. Mã đã quá ngày kết thúc hoặc đã hết số lượng phát hành.\n"
                "  2. Giá trị đơn hàng chưa đạt mức **Đơn hàng tối thiểu** của mã.\n"
                "  3. Chọn sai phạm vi áp dụng (ví dụ dùng mã *Khu vui chơi* khi chưa đặt kèm vé vui chơi) hoặc kỳ nghỉ rơi vào **ngày lễ** bị giới hạn số mã.\n"
                "- **Cách xử lý**: Kiểm tra lại điều kiện đơn tối thiểu/ngày áp dụng trên bảng chọn mã, hoặc liên hệ số điện thoại chi nhánh để Lễ tân kiểm tra hiệu lực mã và hỗ trợ áp mã trực tiếp trên hóa đơn."
            ),
            category="vouchers",
            audience="customer",
        ),
        RagChunk(
            chunk_id="policy:services_and_qr_tickets",
            source="Dịch vụ & Vé khu vui chơi QR",
            title="Đặt dịch vụ chi nhánh, mua vé khu vui chơi & soát vé bằng mã QR",
            content=(
                "- **Vé khu vui chơi QR**: Khách có thể mua vé kèm phòng hoặc mua trực tiếp tại mục **Soát vé QR & Dịch vụ** để nhận mã vé QR điện tử dùng tại cổng. Giá vé phân theo đối tượng: *Người lớn* (trên 140cm), *Trẻ em* (100–140cm) và *Người cao tuổi* (từ 60 tuổi trở lên).\n"
                "- **Dịch vụ chi nhánh (Spa, Ẩm thực, Đưa đón...)**: Khi khách tự đặt, chi phí ghi nhận ngay kèm QR thanh toán. Khi nhân viên/quản lý đặt dịch vụ hộ khách, hệ thống gửi **thông báo xác nhận** về tài khoản khách trước khi tính vào hóa đơn."
            ),
            category="services",
            audience="customer",
        ),
        RagChunk(
            chunk_id="ops:rbac_and_operations",
            source="Quy trình vận hành nội bộ",
            title="Phân quyền chi nhánh, vận hành lễ tân, phân ca và báo cáo BI",
            content=(
                "Nhân viên và Quản lý chi nhánh chỉ xem và thao tác dữ liệu thuộc các chi nhánh được phân công. "
                "Quản trị viên (Admin) quản lý toàn bộ 10 chi nhánh trên 3 miền, xem báo cáo doanh thu, công suất phòng, nhật ký kiểm toán "
                "và lịch phân ca nhân viên. Hệ thống tự động kiểm tra chống trùng lịch phòng giữa khoảng ngày check-in và check-out trước khi lưu đơn."
            ),
            category="operations",
            audience="ops",
        ),
    ]


def _load_db_catalog_chunks() -> list[RagChunk]:
    chunks: list[RagChunk] = []
    try:
        branches = fetch_all("SELECT MaCN, TenCN, DiaChi, SDT FROM CHI_NHANH ORDER BY MaCN")
        branch_map: dict[int, dict[str, Any]] = {}
        region_groups: dict[str, list[str]] = {"Miền Bắc": [], "Miền Trung": [], "Miền Nam": []}

        for b in branches:
            b_id = int(b["MaCN"])
            branch_map[b_id] = b
            region = _classify_region(f"{b['TenCN']} {b.get('DiaChi', '')}")
            region_groups.setdefault(region, []).append(
                f"- **{b['TenCN']}**: {b.get('DiaChi', '')} (SĐT: {b.get('SDT', '')})"
            )

        dir_lines: list[str] = []
        for reg in ("Miền Bắc", "Miền Trung", "Miền Nam"):
            items = region_groups.get(reg) or []
            if items:
                dir_lines.append(f"**{reg} ({len(items)} chi nhánh):**")
                dir_lines.extend(items)
        chunks.append(
            RagChunk(
                chunk_id="system:branches_directory",
                source="Hệ thống chi nhánh 3 miền",
                title="Danh sách 10 chi nhánh theo 3 miền (Miền Bắc, Miền Trung, Miền Nam)",
                content="\n".join(dir_lines),
                category="branches",
                audience="customer",
            )
        )

        room_types_summary = fetch_all(
            """
            SELECT lp.MaLP, lp.TenLP, lp.SucChua, MIN(bg.GiaPhong) AS GiaMin, MAX(bg.GiaPhong) AS GiaMax
            FROM LOAI_PHONG lp
            LEFT JOIN BANG_GIA bg ON bg.MaLP = lp.MaLP
            GROUP BY lp.MaLP, lp.TenLP, lp.SucChua
            ORDER BY lp.SucChua, GiaMin
            """
        )
        if room_types_summary:
            rt_lines = [
                f"- **{r['TenLP']}** (tối đa {r['SucChua']} khách): từ {int(r['GiaMin'] or 0):,}đ đến {int(r['GiaMax'] or 0):,}đ/đêm (tùy mùa & ngày lễ)"
                for r in room_types_summary
            ]
            chunks.append(
                RagChunk(
                    chunk_id="system:room_types_overview",
                    source="Hạng phòng & Bảng giá",
                    title="Tổng hợp các hạng phòng (Standard, Superior, Deluxe, Family, Suite, Presidential Suite)",
                    content="\n".join(rt_lines),
                    category="rooms",
                    audience="customer",
                )
            )

        room_rows = fetch_all(
            """
            SELECT p.MaCN, lp.TenLP, lp.SucChua,
                   COALESCE(fn_gia_phong_theo_ngay(lp.MaLP, CURRENT_DATE()), MIN(bg.GiaPhong)) AS GiaHomNay,
                   MAX(bg.GiaPhong) AS GiaCaoDiem,
                   COUNT(DISTINCT p.MaPhong) AS SoLuongPhong,
                   GROUP_CONCAT(DISTINCT p.SoPhong ORDER BY p.SoPhong SEPARATOR ', ') AS DanhSachPhong
            FROM PHONG p
            JOIN LOAI_PHONG lp ON lp.MaLP = p.MaLP
            LEFT JOIN BANG_GIA bg ON bg.MaLP = lp.MaLP
            GROUP BY p.MaCN, lp.TenLP, lp.SucChua
            ORDER BY p.MaCN, GiaHomNay DESC
            """
        )
        rooms_by_cn: dict[int, list[dict[str, Any]]] = {}
        for r in room_rows:
            rooms_by_cn.setdefault(int(r["MaCN"]), []).append(r)

        parks = fetch_all(
            """
            SELECT kv.MaCN, kv.TenKhu, kv.LoaiKhu, lv.TenLoaiVe, lv.DoiTuong, lv.GiaVe
            FROM KHU_VUI_CHOI kv
            JOIN LOAI_VE lv ON lv.MaKhu = kv.MaKhu
            ORDER BY kv.MaCN, lv.GiaVe DESC
            """
        )
        parks_by_cn: dict[int, list[dict[str, Any]]] = {}
        for pk in parks:
            parks_by_cn.setdefault(int(pk["MaCN"]), []).append(pk)

        services = fetch_all(
            """
            SELECT dcn.MaCN, dv.TenDV, dv.LoaiDV, dcn.DonGia
            FROM DV_CHI_NHANH dcn
            JOIN DICH_VU dv ON dv.MaDV = dcn.MaDV
            WHERE dcn.TrangThai <> 'Tạm ngưng'
            ORDER BY dcn.MaCN, dcn.DonGia
            """
        )
        sv_by_cn: dict[int, list[dict[str, Any]]] = {}
        for sv in services:
            sv_by_cn.setdefault(int(sv["MaCN"]), []).append(sv)

        combos = fetch_all(
            "SELECT gc.MaCN, gc.TenCombo, gc.GiaGoi, lp.TenLP FROM GOI_COMBO gc JOIN LOAI_PHONG lp ON lp.MaLP = gc.MaLP ORDER BY gc.MaCN, gc.GiaGoi"
        )
        combo_by_cn: dict[int, list[dict[str, Any]]] = {}
        for cb in combos:
            combo_by_cn.setdefault(int(cb["MaCN"]), []).append(cb)

        for b_id, b in branch_map.items():
            region = _classify_region(f"{b['TenCN']} {b.get('DiaChi', '')}")
            lines = [
                f"{b['TenCN']} ({region}) — Địa chỉ: {b.get('DiaChi', '')}. Liên hệ: {b.get('SDT', '')}."
            ]
            b_rooms = rooms_by_cn.get(b_id, [])
            if b_rooms:
                lines.append("Hạng phòng & giá tham khảo:")
                for rr in b_rooms:
                    gia_now = int(float(rr["GiaHomNay"] or 0))
                    gia_peak = int(float(rr["GiaCaoDiem"] or gia_now))
                    lines.append(
                        f"- {rr['TenLP']} ({rr['SucChua']} khách, phòng {rr['DanhSachPhong']}): "
                        f"hôm nay {gia_now:,}đ/đêm (cao điểm/lễ tới {gia_peak:,}đ/đêm)"
                    )
            b_parks = parks_by_cn.get(b_id, [])
            if b_parks:
                lines.append("Khu vui chơi & vé QR:")
                for pk in b_parks[:4]:
                    lines.append(
                        f"- {pk['TenKhu']} ({pk['LoaiKhu']}): {pk['TenLoaiVe']} ({pk['DoiTuong']}) — {int(pk['GiaVe']):,}đ"
                    )
            b_combos = combo_by_cn.get(b_id, [])
            if b_combos:
                lines.append("Combo nổi bật: " + "; ".join(f"{c['TenCombo']} ({int(c['GiaGoi']):,}đ)" for c in b_combos[:3]))
            b_sv = sv_by_cn.get(b_id, [])
            if b_sv:
                lines.append("Dịch vụ nổi bật: " + "; ".join(f"{s['TenDV']} ({int(s['DonGia']):,}đ)" for s in b_sv[:5]))

            chunks.append(
                RagChunk(
                    chunk_id=f"db:branch:{b_id}",
                    source=b["TenCN"],
                    title=f"Thông tin chi tiết phòng, vé vui chơi & dịch vụ tại {b['TenCN']}",
                    content="\n".join(lines),
                    category="branch_catalog",
                    audience="customer",
                    ma_cn=b_id,
                )
            )

        vouchers = fetch_all(
            """
            SELECT Code, LoaiApDung, LoaiGiam, GiaTriGiam, DonHangToiThieu, GiamToiDa
            FROM MA_GIAM_GIA
            WHERE TrangThai = 'Hiệu lực' AND CURRENT_DATE() BETWEEN NgayBatDau AND NgayKetThuc
            ORDER BY GiaTriGiam DESC
            """
        )
        if vouchers:
            lines = [
                f"- {v['Code']} ({v['LoaiApDung']}): giảm {v['GiaTriGiam']} ({v['LoaiGiam']}), đơn tối thiểu {int(v['DonHangToiThieu']):,}đ, tối đa {int(v['GiamToiDa'] or 0):,}đ"
                for v in vouchers[:12]
            ]
            chunks.append(
                RagChunk(
                    chunk_id="db:MA_GIAM_GIA",
                    source="Ưu đãi & Voucher",
                    title="Danh sách mã giảm giá đang áp dụng",
                    content="\n".join(lines),
                    category="vouchers",
                    audience="customer",
                )
            )

        lunar = fetch_all(
            "SELECT TenSuKien, NgayBatDauDuong, NgayKetThucDuong FROM QUY_DOI_LE_AM_LICH WHERE Nam >= 2026 ORDER BY NgayBatDauDuong"
        )
        if lunar:
            lines = [
                f"- {r['TenSuKien']}: từ {r['NgayBatDauDuong']} đến {r['NgayKetThucDuong']}"
                for r in lunar
            ]
            chunks.append(
                RagChunk(
                    chunk_id="db:QUY_DOI_LE_AM_LICH",
                    source="Lịch ngày lễ",
                    title="Lịch nghỉ lễ Âm lịch áp dụng bảng giá lễ (2026–2028)",
                    content="\n".join(lines),
                    category="pricing_rules",
                    audience="customer",
                )
            )
    except Exception:
        pass
    return chunks


def build_rag_index(force: bool = False) -> dict[str, Any]:
    now = time.time()
    if not force and _INDEX_CACHE["docs"] and (now - _INDEX_CACHE["built_at"]) < _CACHE_TTL_SECONDS:
        return _INDEX_CACHE

    docs: list[RagChunk] = []
    docs.extend(_curated_policy_chunks())
    docs.extend(_load_db_catalog_chunks())

    doc_tokens: list[list[str]] = [tokenize(f"{d.title} {d.title} {d.content}") for d in docs]
    df: dict[str, int] = {}
    doc_tf: list[dict[str, int]] = []
    doc_len: list[int] = []
    for toks in doc_tokens:
        tf: dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        doc_tf.append(tf)
        doc_len.append(len(toks))
        for t in tf:
            df[t] = df.get(t, 0) + 1

    n_docs = max(len(docs), 1)
    idf: dict[str, float] = {
        term: math.log(1.0 + (n_docs - freq + 0.5) / (freq + 0.5))
        for term, freq in df.items()
    }
    avgdl = (sum(doc_len) / len(doc_len)) if doc_len else 1.0
    ngram_vecs = [_char_ngrams(f"{d.title} {d.content}", n=3) for d in docs]

    _INDEX_CACHE.update(
        {
            "built_at": now,
            "docs": docs,
            "idf": idf,
            "doc_tf": doc_tf,
            "doc_len": doc_len,
            "avgdl": avgdl,
            "ngram_vecs": ngram_vecs,
        }
    )
    return _INDEX_CACHE


def retrieve_knowledge(
    query: str,
    top_k: int = 4,
    audience: str = "customer",
    ma_cn: int | None = None,
    prefer_categories: tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Pure-CPU Hybrid BM25 (Unigram + Bigram + Accent) + Char 3-gram Cosine fused via RRF."""
    index = build_rag_index()
    docs: list[RagChunk] = index["docs"]
    if not docs or not query.strip():
        return []

    expanded = expand_domain_query(query)
    q_tokens = tokenize(expanded)
    raw_q_tokens = set(tokenize(query))
    q_ngrams = _char_ngrams(expanded, n=3)

    eligible: list[int] = []
    for idx, doc in enumerate(docs):
        if audience != "ops" and doc.audience == "ops":
            continue
        eligible.append(idx)

    if not eligible:
        return []

    idf: dict[str, float] = index["idf"]
    doc_tf: list[dict[str, int]] = index["doc_tf"]
    doc_len: list[int] = index["doc_len"]
    avgdl: float = index["avgdl"] or 1.0
    ngram_vecs: list[dict[str, float]] = index["ngram_vecs"]

    bm25_scores: dict[int, float] = {}
    ngram_scores: dict[int, float] = {}

    for idx in eligible:
        tf_map = doc_tf[idx]
        dl = doc_len[idx] or 1
        bm25 = 0.0
        for tok in q_tokens:
            f = tf_map.get(tok, 0)
            if f <= 0:
                continue
            term_idf = idf.get(tok, 0.0)
            denom = f + _BM25_K1 * (1.0 - _BM25_B + _BM25_B * (dl / avgdl))
            weight = 1.35 if "_" in tok else 1.0
            bm25 += weight * term_idf * (f * (_BM25_K1 + 1.0)) / denom
        bm25_scores[idx] = bm25

        d_ng = ngram_vecs[idx]
        ngram_scores[idx] = sum(q_ngrams[g] * d_ng.get(g, 0.0) for g in q_ngrams)

    bm25_ranked = sorted(eligible, key=lambda i: bm25_scores[i], reverse=True)
    ngram_ranked = sorted(eligible, key=lambda i: ngram_scores[i], reverse=True)
    bm25_rank_pos = {doc_idx: rank + 1 for rank, doc_idx in enumerate(bm25_ranked)}
    ngram_rank_pos = {doc_idx: rank + 1 for rank, doc_idx in enumerate(ngram_ranked)}

    fused: list[tuple[float, RagChunk]] = []
    for idx in eligible:
        if bm25_scores[idx] <= 0.0 and ngram_scores[idx] < 0.14:
            continue
        doc = docs[idx]
        rrf_score = (1.0 / (_RRF_K + bm25_rank_pos[idx])) + (0.7 / (_RRF_K + ngram_rank_pos[idx]))
        title_overlap = len(raw_q_tokens & set(tokenize(doc.title)))
        rrf_score += 0.005 * title_overlap
        if ma_cn is not None and doc.ma_cn == int(ma_cn):
            rrf_score += 0.015
        if prefer_categories and doc.category in prefer_categories:
            rrf_score += 0.010
        fused.append((rrf_score, doc))

    fused.sort(key=lambda item: item[0], reverse=True)
    results: list[dict[str, Any]] = []
    for score, doc in fused[:top_k]:
        snippet = doc.content.strip().replace("\r\n", "\n")
        if len(snippet) > 1200:
            snippet = snippet[:1197] + "..."
        results.append(
            {
                "id": doc.chunk_id,
                "source": doc.source,
                "title": doc.title,
                "category": doc.category,
                "ma_cn": doc.ma_cn,
                "score": round(float(score), 4),
                "snippet": snippet,
            }
        )
    return results
