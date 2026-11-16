from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import math
import re
from typing import Any

from .rag_engine import strip_accents

_INTENT_EXEMPLARS: dict[str, tuple[str, ...]] = {
    "search_rooms": (
        "tìm phòng trống tại chi nhánh theo ngày nhận phòng ngày trả phòng",
        "khách sạn còn phòng đôi cho 2 người không và giá mỗi đêm bao nhiêu",
        "kiểm tra phòng còn trống ở đà nẵng cuối tuần này cho 4 khách",
        "tôi muốn đặt phòng deluxe hoặc superior dịp 30/4 còn chỗ không",
        "xem giá phòng 3 ngày 2 đêm tại phú quốc từ ngày 10 tháng 6",
        "còn phòng trống ngày mai cho gia đình 4 người không",
        "giá phòng mỗi đêm khoảng bao nhiêu khi đặt từ 2026-06-10 đến 2026-06-12",
        "kiểm tra tình trạng phòng trống chi nhánh nha trang",
        "tôi định đi du lịch hội an 2 đêm muốn hỏi phòng trống và giá",
        "phòng presidential suite ở hà nội còn trống không",
        "dat phong khach san con trong khong gia bao nhieu mot dem",
        "tim phong cho 2 nguoi o sai gon ngay cuoi tuan",
    ),
    "price_ranking": (
        "liệt kê phòng có giá cao nhất đắt nhất của từng chi nhánh",
        "chi nhánh nào có phòng rẻ nhất bình dân tiết kiệm nhất",
        "so sánh giá hạng phòng vip nhất sang nhất giữa các chi nhánh",
        "ở phú quốc phòng nào đắt tiền nhất và phòng nào rẻ nhất",
        "top hạng phòng giá cao nhất mỗi chi nhánh",
        "tổng hợp giá phòng thấp nhất ở tất cả các chi nhánh",
        "phong dat nhat re nhat cua tung chi nhanh",
    ),
    "voucher_advice": (
        "hiện tại khách sạn có mã giảm giá hay chương trình khuyến mãi nào không",
        "gợi ý voucher ưu đãi giảm nhiều nhất khi đặt phòng",
        "cách áp dụng nhập chọn mã giảm giá ở bước thanh toán như thế nào",
        "ngày lễ 30/4 được dùng tối đa mấy voucher nếu đặt kèm khu vui chơi",
        "quy tắc chọn mã giảm giá ngày thường và ngày lễ ra sao",
        "tôi có được dùng 2 mã ưu đãi cùng lúc không",
        "lam sao de su dung voucher khuyen mai khi dat phong online",
    ),
    "catalog_highlights": (
        "ở chi nhánh này có khu vui chơi giải trí trò chơi gì nổi bật",
        "giá vé cổng công viên nước vinwonders trẻ em người lớn bao nhiêu",
        "tại phú quốc có những loại vé khu vui chơi và gói combo nào",
        "khách sạn có dịch vụ spa massage buffet nhà hàng gì không",
        "cho xem danh sách dịch vụ thư giãn và giá vé trò chơi tại đà nẵng",
        "thế còn vé vui chơi và các gói combo ở đó thì sao",
        "mua vé khu vui chơi riêng không đặt phòng có những loại vé nào",
    ),
    "my_bookings": (
        "kiểm tra đơn đặt phòng booking của tôi hiện tại thế nào",
        "xem danh sách thông báo và mã xác nhận otp của tôi",
        "lịch sử đặt phòng và hóa đơn của mình có đơn nào đang chờ xác nhận",
        "tài khoản của tôi có thông báo xác nhận dịch vụ nhân viên đặt hộ không",
        "tra cứu đơn của tôi xem đã thanh toán cọc hay đã hủy chưa",
        "cho xem thông báo cá nhân và trạng thái booking của tôi",
    ),
    "policy_faq": (
        "khi đặt phòng trực tiếp tại khách sạn có thể thanh toán bằng tiền mặt hoặc thẻ không",
        "có những phương thức thanh toán nào hỗ trợ vietqr đặt cọc 30% không",
        "nếu tôi hủy đặt phòng trước khi nhận phòng thì có mất phí hủy hay được hoàn tiền cọc không",
        "quy định hủy phòng hoàn cọc và xác thực otp tại quầy như thế nào",
        "tôi đã đặt phòng nhưng muốn thay đổi ngày nhận phòng trả phòng thì có bị tính thêm phí không",
        "có thể tự chỉnh sửa dời lịch ngày check-in sau khi đã đặt không",
        "nếu đặt 2 phòng cùng lúc thì mã giảm giá áp dụng cho cả hai phòng hay một hóa đơn",
        "tôi nhập mã ưu đãi nhưng hệ thống thông báo mã không hợp lệ hoặc hết hạn thì xử lý thế nào",
        "nhập code giảm giá mà web báo lỗi không áp được thì tại sao",
        "tại sao chọn voucher khuyến mãi không dùng được hoặc không được giảm tiền",
        "tổng chi phí thanh toán bao gồm những gì có tính thêm thuế vat hay phí dịch vụ phụ thu không",
        "website có hiển thị bảng kê chi tiết hóa đơn từng đêm tiền phòng dịch vụ không",
        "thủ tục nhận phòng check in cần mang giấy tờ cccd gì có hỗ trợ nhận sớm trả muộn không",
        "trẻ em đi cùng có tính thêm phí hay áp dụng giá vé khu vui chơi theo chiều cao thế nào",
        "hệ thống khách sạn có những chi nhánh nào ở miền bắc miền trung miền nam địa chỉ số điện thoại",
        "quy trình đặt cọc chuyển khoản đối soát tự động khi đặt online hoạt động ra sao",
        "các hạng phòng tiêu chuẩn đến tổng thống có sức chứa bao nhiêu người",
        "đặt phòng xong khi nào nhận được xác nhận qua email hay thông báo và biết phòng được giữ chắc chắn",
        "tôi đến khách sạn rất muộn ban đêm sau 22h thì phòng có bị hủy không",
        "tôi muốn xuất hóa đơn đỏ hóa đơn vat công tác hoặc thanh toán trả sau tại khách sạn",
        "nâng cấp sang hạng phòng khác hoặc đổi ngày sau khi đặt phòng thì làm thế nào",
        "nếu hủy phòng có được hoàn lại 100 phần trăm tiền đã cọc hoặc thanh toán không",
        "vé khu vui chơi đặt trên web là vé cứng hay vé điện tử qr có cần in ra giấy không",
    ),
    "bi_analytics": (
        "tóm tắt báo cáo doanh thu và công suất lấp đầy phòng các chi nhánh",
        "xem thống kê tình hình kinh doanh bi tỷ lệ hủy phòng top dịch vụ doanh thu cao",
        "chi nhánh nào có doanh thu và công nợ cao nhất hiện tại",
        "xem chỉ số vận hành công suất phòng các chi nhánh được phép xem",
        "bao cao doanh thu cong suat lap day phong he thong bi",
    ),
    "admin_sql": (
        "chạy câu lệnh sql select thống kê top 5 loại phòng giá cao nhất",
        "truy vấn sql xem danh sách voucher hoặc top chi nhánh",
        "thực thi truy vấn dữ liệu bảng ma_giam_gia bằng sql",
    ),
    "greeting_or_help": (
        "xin chào bạn có thể giúp gì cho tôi",
        "hello hi trợ lý ảo aurelia làm được những gì",
        "cảm ơn bạn nhé tạm biệt",
        "bạn hỗ trợ được các thông tin gì về khách sạn",
    ),
    "out_of_scope": (
        "hôm nay thời tiết hà nội nắng hay mưa bao nhiêu độ",
        "viết giúp tôi đoạn code python sắp xếp mảng quicksort",
        "giá vàng hôm nay chứng khoán thế nào đội nào vô địch world cup",
        "giải phương trình bậc hai hoặc dịch đoạn văn tiếng anh này giúp tôi",
        "hướng dẫn cách nấu phở bò tại nhà ngon chuẩn vị",
    ),
}

_BRANCH_ALIASES: tuple[tuple[str, str], ...] = (
    ("da nang", "Đà Nẵng"),
    ("my khe", "Đà Nẵng"),
    ("ba na", "Đà Nẵng"),
    ("phu quoc", "Phú Quốc"),
    ("kien giang", "Phú Quốc"),
    ("bai truong", "Phú Quốc"),
    ("ha noi", "Hà Nội"),
    ("hoan kiem", "Hà Nội"),
    ("nha trang", "Nha Trang"),
    ("khanh hoa", "Nha Trang"),
    ("tp.hcm", "TP.HCM"),
    ("tp hcm", "TP.HCM"),
    ("ho chi minh", "TP.HCM"),
    ("sai gon", "TP.HCM"),
    ("da lat", "Đà Lạt"),
    ("lam dong", "Đà Lạt"),
    ("hoi an", "Hội An"),
    ("quang nam", "Hội An"),
    ("sa pa", "Sa Pa"),
    ("sapa", "Sapa"),
    ("lao cai", "Sa Pa"),
    ("ha long", "Hạ Long"),
    ("quang ninh", "Hạ Long"),
    ("bai chay", "Hạ Long"),
    ("hue", "Huế"),
    ("thua thien hue", "Huế"),
    ("vung tau", "Vũng Tàu"),
    ("phan thiet", "Phan Thiết"),
    ("can tho", "Cần Thơ"),
    ("quy nhon", "Quy Nhơn"),
)

_ROOM_TYPES: tuple[tuple[str, str], ...] = (
    ("presidential", "Presidential Suite"),
    ("tong thong", "Presidential Suite"),
    ("family", "Family"),
    ("gia dinh", "Family"),
    ("deluxe", "Deluxe"),
    ("superior", "Superior"),
    ("suite", "Suite"),
    ("standard", "Standard"),
    ("tieu chuan", "Standard"),
)

_STOP_FOR_INTENT = {"va", "la", "cua", "cho", "co", "khong", "duoc", "nhung", "cac", "nay", "thi", "ma", "nhe", "a"}


def _router_tokens(text: str) -> dict[str, float]:
    """Build hybrid token map: folded unigrams + word bigrams + accented senses + light char 3-grams."""
    lowered = text.lower()
    raw = re.findall(r"[0-9a-zà-ỹ]+", lowered)
    folded_seq: list[str] = []
    weights: dict[str, float] = {}

    for tok in raw:
        folded = strip_accents(tok)
        if len(folded) <= 1 and not folded.isdigit():
            continue
        if folded not in _STOP_FOR_INTENT:
            weights[f"w:{folded}"] = weights.get(f"w:{folded}", 0.0) + 1.0
            if tok != folded:
                weights[f"ac:{tok}"] = weights.get(f"ac:{tok}", 0.0) + 1.15
        folded_seq.append(folded)

    for i in range(len(folded_seq) - 1):
        bg = f"bg:{folded_seq[i]}_{folded_seq[i + 1]}"
        weights[bg] = weights.get(bg, 0.0) + 1.6

    cleaned = re.sub(r"[^0-9a-z]+", " ", strip_accents(lowered)).strip()
    for i in range(max(0, len(cleaned) - 2)):
        g = cleaned[i : i + 3]
        if g.strip():
            weights[f"c3:{g}"] = weights.get(f"c3:{g}", 0.0) + 0.35
    return weights


def _build_router_index() -> dict[str, Any]:
    doc_feats: list[tuple[str, dict[str, float]]] = []
    df: dict[str, int] = {}
    for intent, exemplars in _INTENT_EXEMPLARS.items():
        for ex in exemplars:
            tf = _router_tokens(ex)
            doc_feats.append((intent, tf))
            for term in tf:
                df[term] = df.get(term, 0) + 1

    n_docs = len(doc_feats) or 1
    idf = {term: math.log(1.0 + n_docs / (freq + 1.0)) for term, freq in df.items()}

    vectors: list[tuple[str, dict[str, float]]] = []
    for intent, tf in doc_feats:
        vec = {term: val * idf.get(term, 1.0) for term, val in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append((intent, {term: v / norm for term, v in vec.items()}))

    return {"idf": idf, "vectors": vectors}


_ROUTER_INDEX = _build_router_index()


def _score_intents(message: str) -> dict[str, float]:
    idf: dict[str, float] = _ROUTER_INDEX["idf"]
    tf = _router_tokens(message)
    q_vec = {term: val * idf.get(term, 0.8) for term, val in tf.items()}
    norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
    q_vec = {term: v / norm for term, v in q_vec.items()}

    per_intent: dict[str, list[float]] = {k: [] for k in _INTENT_EXEMPLARS}
    for intent, vec in _ROUTER_INDEX["vectors"]:
        sim = sum(q_vec[t] * vec.get(t, 0.0) for t in q_vec)
        per_intent[intent].append(sim)

    scores: dict[str, float] = {}
    for intent, sims in per_intent.items():
        sims.sort(reverse=True)
        top1 = sims[0] if sims else 0.0
        top2 = sum(sims[:2]) / min(len(sims), 2) if sims else 0.0
        scores[intent] = round(0.65 * top1 + 0.35 * top2, 4)
    return scores


def extract_dates(message: str) -> tuple[str | None, str | None]:
    found: list[date] = []
    # YYYY-MM-DD or YYYY/MM/DD
    for match in re.finditer(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", message):
        try:
            found.append(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
        except ValueError:
            pass
    # DD/MM[/YYYY] or DD-MM[-YYYY]
    for match in re.finditer(r"\b(\d{1,2})[-/](\d{1,2})(?:[-/](\d{4}))?\b", message):
        # Avoid re-matching trailing part of YYYY-MM-DD
        if match.start() > 0 and message[match.start() - 1].isdigit():
            continue
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3)) if match.group(3) else date.today().year
        try:
            parsed = date(year, month, day)
            if not match.group(3) and parsed < date.today() - timedelta(days=30):
                parsed = date(year + 1, month, day)
            found.append(parsed)
        except ValueError:
            pass
    # "ngày DD tháng MM [năm YYYY]"
    norm = strip_accents(message.lower())
    for match in re.finditer(r"\bngay\s+(\d{1,2})\s+thang\s+(\d{1,2})(?:\s+nam\s+(\d{4}))?\b", norm):
        day, month = int(match.group(1)), int(match.group(2))
        year = int(match.group(3)) if match.group(3) else date.today().year
        try:
            parsed = date(year, month, day)
            if not match.group(3) and parsed < date.today() - timedelta(days=30):
                parsed = date(year + 1, month, day)
            found.append(parsed)
        except ValueError:
            pass

    nights_hint: int | None = None
    m_nights = re.search(r"\b(\d+)\s*dem\b", norm)
    if m_nights:
        nights_hint = max(1, min(30, int(m_nights.group(1))))

    if not found:
        today = date.today()
        if "tet" in norm:
            return "2026-02-17", "2026-02-19"
        if "quoc khanh" in norm or "2/9" in message:
            return "2026-09-02", "2026-09-04"
        if "30/4" in message or "1/5" in message:
            return "2026-04-30", "2026-05-02"
        if "hung vuong" in norm or "gio to" in norm:
            return "2026-04-26", "2026-04-28"
        if "ngay mai" in norm or "tu mai" in norm:
            ci = today + timedelta(days=1)
            return ci.isoformat(), (ci + timedelta(days=nights_hint or 2)).isoformat()
        if "hom nay" in norm:
            return today.isoformat(), (today + timedelta(days=nights_hint or 1)).isoformat()
        if "cuoi tuan" in norm:
            days_until_sat = (5 - today.weekday()) % 7 or 7
            sat = today + timedelta(days=days_until_sat)
            return sat.isoformat(), (sat + timedelta(days=nights_hint or 2)).isoformat()
        if nights_hint:
            # Explicit stay duration (e.g. "3 ngày 2 đêm") without start date -> only signal duration if needed
            return None, None
        return None, None

    if len(found) == 1:
        checkin = found[0]
        return checkin.isoformat(), (checkin + timedelta(days=nights_hint or 2)).isoformat()

    checkin = found[0]
    checkout = found[1]
    if checkout <= checkin:
        checkout = checkin + timedelta(days=nights_hint or 1)
    return checkin.isoformat(), checkout.isoformat()


def extract_branch_keyword(message: str) -> str | None:
    norm = strip_accents(message.lower())
    for alias, canonical in _BRANCH_ALIASES:
        if re.search(rf"(?<![0-9a-z]){re.escape(alias)}(?![0-9a-z])", norm):
            return canonical
    cn_match = re.search(r"\b(?:chi nhanh|cn)\s*(\d+)\b", norm)
    if cn_match:
        return cn_match.group(1)
    return None


def extract_region(message: str) -> str | None:
    norm = strip_accents(message.lower())
    if "mien bac" in norm:
        return "Miền Bắc"
    if "mien trung" in norm:
        return "Miền Trung"
    if "mien nam" in norm:
        return "Miền Nam"
    return None


def extract_room_type_hint(message: str) -> str | None:
    norm = strip_accents(message.lower())
    for cue, canonical in _ROOM_TYPES:
        if re.search(rf"(?<![0-9a-z]){re.escape(cue)}(?![0-9a-z])", norm):
            return canonical
    return None


def extract_capacity(message: str) -> int:
    norm = strip_accents(message.lower())
    match = re.search(r"\b(\d+)\s*(?:nguoi|khach|adult|guest|lon)\b", norm)
    if match:
        return max(1, min(10, int(match.group(1))))
    if "cap doi" in norm or "phong doi" in norm or "2 vo chong" in norm:
        return 2
    if "gia dinh" in norm:
        return 4
    return 2


def extract_sql_snippet(message: str) -> str | None:
    fenced = re.search(r"```(?:sql)?\s*((?:SELECT|WITH)[\s\S]+?)```", message, flags=re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    inline = re.search(r"\b((?:SELECT|WITH)\s+[\s\S]+)$", message, flags=re.IGNORECASE)
    if inline:
        return inline.group(1).strip()
    return None


def extract_history_context(history: list[dict[str, str]] | None) -> dict[str, Any]:
    ctx: dict[str, Any] = {"branch_kw": None, "checkin": None, "checkout": None, "capacity": None}
    if not history:
        return ctx
    for turn in reversed(history[-6:]):
        text = str(turn.get("content") or "")
        if not text:
            continue
        if not ctx["branch_kw"]:
            ctx["branch_kw"] = extract_branch_keyword(text)
        if not ctx["checkin"]:
            ci, co = extract_dates(text)
            if ci:
                ctx["checkin"], ctx["checkout"] = ci, co
        if not ctx["capacity"]:
            cap_norm = strip_accents(text.lower())
            if re.search(r"\b(\d+)\s*(?:nguoi|khach|adult|guest)\b", cap_norm):
                ctx["capacity"] = extract_capacity(text)
        if ctx["branch_kw"] and ctx["checkin"] and ctx["capacity"]:
            break
    return ctx


@dataclass
class RouteDecision:
    primary_intent: str
    active_intents: set[str] = field(default_factory=set)
    scores: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    slots: dict[str, Any] = field(default_factory=dict)


def classify_intent(
    message: str,
    history: list[dict[str, str]] | None = None,
    explicit_ma_cn: int | None = None,
) -> RouteDecision:
    """Whole-utterance CPU semantic intent router + structured slot extraction."""
    norm = strip_accents(message.lower()).strip()
    scores = _score_intents(message)

    hist_ctx = extract_history_context(history)
    branch_kw = extract_branch_keyword(message)
    region = extract_region(message)
    room_type_hint = extract_room_type_hint(message)
    checkin, checkout = extract_dates(message)
    capacity = extract_capacity(message)
    sql_snippet = extract_sql_snippet(message)

    refers_prior_place = bool(
        re.search(r"\b(o do|cho do|chi nhanh do|chi nhanh nay|noi do|tai day|o day|the con|con ve)\b", norm)
    )
    asks_all_branches = bool(
        re.search(r"\b(tung chi nhanh|moi chi nhanh|cac chi nhanh|tat ca chi nhanh|toan he thong)\b", norm)
    )
    has_personal_cue = bool(
        re.search(
            r"\b(cua toi|cua minh|cua em|booking cua|don dat cua|don cua toi|thong bao cua|xem thong bao|lich su dat|kiem tra don|ho so cua)\b",
            norm,
        )
    )
    has_amusement_cue = bool(
        re.search(r"\b(khu vui choi|cong vien|vinwonders|safari|tro choi|ve cong|ve vui choi|vui choi|giai tri)\b", norm)
    )
    price_order = "asc" if re.search(r"\b(re nhat|thap nhat|tiet kiem|binh dan)\b", norm) else "desc"

    # Carry over branch / dates only for follow-up turns
    if not branch_kw and not asks_all_branches and not region and refers_prior_place:
        branch_kw = hist_ctx.get("branch_kw")
    elif not branch_kw and not asks_all_branches and not region and scores["policy_faq"] < max(scores["search_rooms"], scores["catalog_highlights"]):
        # Gentle history carry-over for concrete booking/catalog follow-ups
        if hist_ctx.get("branch_kw") and not re.search(r"\b(quy dinh|chinh sach|huy phong|doi ngay|tien mat|hoa don|thue)\b", norm):
            branch_kw = hist_ctx.get("branch_kw")
    if not checkin and refers_prior_place:
        checkin, checkout = hist_ctx.get("checkin"), hist_ctx.get("checkout")
    if capacity == 2 and hist_ctx.get("capacity") and refers_prior_place:
        capacity = hist_ctx["capacity"]

    slots: dict[str, Any] = {
        "branch_kw": branch_kw,
        "region": region,
        "room_type_hint": room_type_hint,
        "checkin": checkin,
        "checkout": checkout,
        "capacity": capacity,
        "sql_snippet": sql_snippet,
        "price_order": price_order,
        "asks_all_branches": asks_all_branches,
        "refers_prior_place": refers_prior_place,
        "has_personal_cue": has_personal_cue,
        "has_amusement_cue": has_amusement_cue,
        "explicit_ma_cn": explicit_ma_cn,
    }

    # Explicit SQL override
    if sql_snippet or (re.search(r"\bsql\b", norm) and scores["admin_sql"] >= 0.14):
        return RouteDecision(
            primary_intent="admin_sql",
            active_intents={"admin_sql"},
            scores=scores,
            confidence=max(0.85, scores["admin_sql"]),
            slots=slots,
        )

    domain_intents = (
        "search_rooms",
        "price_ranking",
        "voucher_advice",
        "catalog_highlights",
        "my_bookings",
        "policy_faq",
        "bi_analytics",
        "admin_sql",
    )
    best_domain = max(domain_intents, key=lambda k: scores[k])
    best_domain_score = scores[best_domain]
    greet_score = scores["greeting_or_help"]
    oos_score = scores["out_of_scope"]

    # Detect non-domain / greeting / out-of-scope gracefully (even if city/date word like "hôm nay ở Hà Nội" appears)
    has_hotel_vocab = bool(
        re.search(
            r"\b(phong|khach san|resort|dat|voucher|khuyen mai|uu dai|ve|khu vui choi|chi nhanh|hoa don|coc|huy|spa|buffet|combo|gia|otp|nhan phong|tra phong)\b",
            norm,
        )
    )
    if oos_score >= max(best_domain_score + 0.04, 0.20) and not has_hotel_vocab:
        return RouteDecision("out_of_scope", {"out_of_scope"}, scores, oos_score, slots)

    has_any_slot = bool(branch_kw or region or checkin or room_type_hint or has_personal_cue or has_amusement_cue)
    if not has_any_slot:
        if greet_score >= max(best_domain_score, oos_score, 0.22):
            return RouteDecision("greeting_or_help", {"greeting_or_help"}, scores, greet_score, slots)
        if oos_score > best_domain_score + 0.04 or best_domain_score < 0.13:
            return RouteDecision("out_of_scope", {"out_of_scope"}, scores, max(oos_score, 1.0 - best_domain_score), slots)

    # Disambiguate subtle structural conflicts cleanly
    # 1) Compare price across branches strongly favors price_ranking over search_rooms
    if re.search(r"\b(dat nhat|dat tien|cao nhat|re nhat|thap nhat|vip nhat|sang nhat|so sanh gia)\b", norm) and re.search(r"\b(phong|hang|gia)\b", norm):
        best_domain = "price_ranking"
        best_domain_score = max(scores["price_ranking"], best_domain_score)

    # 2) my_bookings requires personal ownership cue OR strong margin over policy_faq
    if best_domain == "my_bookings" and not has_personal_cue and scores["policy_faq"] >= scores["my_bookings"] * 0.85:
        best_domain = "policy_faq"
        best_domain_score = scores["policy_faq"]

    active: set[str] = {best_domain}

    # Multi-intent composition when multiple capabilities have clear semantic relevance
    for candidate in ("search_rooms", "price_ranking", "voucher_advice", "catalog_highlights", "policy_faq"):
        if candidate == best_domain:
            continue
        cand_score = scores[candidate]
        if cand_score >= 0.23 and cand_score >= 0.72 * best_domain_score:
            if best_domain == "policy_faq" and candidate in ("search_rooms", "catalog_highlights") and not checkin and not branch_kw:
                continue
            if best_domain == "price_ranking" and candidate == "search_rooms":
                continue
            active.add(candidate)

    # Structural multi-intent boosts (e.g., user explicitly gives check-in dates + asks about vouchers or vice-versa)
    if checkin and branch_kw and best_domain in ("voucher_advice", "catalog_highlights") and scores["search_rooms"] >= 0.15:
        active.add("search_rooms")
    if "search_rooms" in active and (scores["voucher_advice"] >= 0.21 or re.search(r"\b(voucher|ma giam|khuyen mai|uu dai)\b", norm)):
        if "khong hop le" not in norm and "het han" not in norm and "2 phong" not in norm:
            active.add("voucher_advice")
    if "voucher_advice" in active and re.search(r"\b(cach ap dung|buoc thanh toan|su dung ma|ngay le|ngay thuong)\b", norm):
        active.add("policy_faq")

    return RouteDecision(
        primary_intent=best_domain,
        active_intents=active,
        scores=scores,
        confidence=best_domain_score,
        slots=slots,
    )
