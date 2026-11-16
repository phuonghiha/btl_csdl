from __future__ import annotations

import re
import time
from typing import Any

from fastapi import HTTPException
import httpx

from app.config import get_settings
from app.services.agent_tools import (
    resolve_branch,
    resolve_branches_by_region,
    tool_bi_branch_analytics,
    tool_get_catalog_highlights,
    tool_get_my_bookings_and_notifications,
    tool_recommend_vouchers,
    tool_room_price_rankings,
    tool_run_safe_readonly_sql,
    tool_search_available_rooms,
)
from app.services.intent_router import classify_intent
from app.services.rag_engine import build_rag_index, retrieve_knowledge, strip_accents


def _resolve_agent_mode(user: dict[str, Any] | None) -> str:
    if not user:
        return "public_concierge"
    if user.get("MaKH") and not user.get("is_admin"):
        perms = set(user.get("permissions") or [])
        if "REPORT.READ_BRANCH" not in perms and "BOOKING.READ_BRANCH" not in perms:
            return "customer_concierge"
    return "ops_bi_analyst"


def capabilities_role_label(user: dict[str, Any] | None) -> str:
    if not user:
        return "Khách vãng lai"
    roles = user.get("role_names") or []
    if roles:
        return ", ".join(str(r) for r in roles)
    return str(user.get("TenDangNhap") or "Người dùng")


def _allowed_tool_names(user: dict[str, Any] | None) -> list[str]:
    mode = _resolve_agent_mode(user)
    if mode == "ops_bi_analyst":
        tools = [
            "retrieve_knowledge",
            "search_available_rooms",
            "room_price_rankings",
            "recommend_vouchers",
            "get_catalog_highlights",
            "bi_branch_analytics",
        ]
        if user and user.get("is_admin"):
            tools.append("run_safe_readonly_sql")
        return tools
    tools = [
        "retrieve_knowledge",
        "search_available_rooms",
        "room_price_rankings",
        "recommend_vouchers",
        "get_catalog_highlights",
    ]
    if mode == "customer_concierge":
        tools.append("get_my_bookings_and_notifications")
    return tools


def _sample_prompts_for_mode(user: dict[str, Any] | None) -> list[str]:
    mode = _resolve_agent_mode(user)
    if mode == "ops_bi_analyst":
        prompts = [
            "Tóm tắt doanh thu, công suất phòng và trạng thái booking các chi nhánh được phép xem",
            "Quy định cọc 30%, OTP hủy phòng và chống trùng lịch đặt phòng như thế nào?",
            "Kiểm tra phòng trống chi nhánh Đà Nẵng từ 2026-06-10 đến 2026-06-12 cho 2 khách",
        ]
        if user and user.get("is_admin"):
            prompts.append("Chạy SQL thống kê top 5 loại phòng có giá niêm yết cao nhất hệ thống")
        return prompts
    if mode == "customer_concierge":
        return [
            "Tìm phòng trống Đà Nẵng từ 2026-06-10 đến 2026-06-12 cho 2 người và gợi ý voucher tối ưu",
            "Liệt kê phòng có giá cao nhất của từng chi nhánh",
            "Ngày lễ 30/4 được dùng mấy voucher nếu chỉ đặt khách sạn hoặc kèm khu vui chơi?",
            "Kiểm tra booking và thông báo xác nhận OTP / dịch vụ hiện có của tôi",
        ]
    return [
        "Tìm phòng trống Đà Nẵng từ 2026-06-10 đến 2026-06-12 cho 2 người",
        "Liệt kê phòng có giá cao nhất của từng chi nhánh",
        "Ngày lễ được chọn tối đa mấy voucher? Quy định đặt cọc 30% và hủy phòng ra sao?",
        "Chi nhánh Phú Quốc có khu vui chơi và dịch vụ gì nổi bật?",
    ]


def get_agent_capabilities(user: dict[str, Any] | None) -> dict[str, Any]:
    settings = get_settings()
    rag_index = build_rag_index()
    mode = _resolve_agent_mode(user)
    gemini_configured = bool(settings.gemini_api_key)
    return {
        "mode": mode,
        "engine": "gemini_rag_agent" if gemini_configured else "local_hybrid_rag",
        "gemini_configured": gemini_configured,
        "gemini_model": settings.gemini_model if gemini_configured else None,
        "rag_chunks_count": len(rag_index.get("docs", [])),
        "allowed_tools": _allowed_tool_names(user),
        "sample_prompts": _sample_prompts_for_mode(user),
        "branch_ids": (user or {}).get("branch_ids", []),
        "role_name": capabilities_role_label(user),
    }


def _build_local_nl_sql(message: str) -> str | None:
    norm = strip_accents(message.lower())
    if "top" in norm and ("loai phong" in norm or "gia" in norm):
        return (
            "SELECT lp.MaLP, lp.TenLP, lp.SucChua, MAX(bg.GiaPhong) AS GiaCaoNhat "
            "FROM LOAI_PHONG lp "
            "JOIN BANG_GIA bg ON bg.MaLP = lp.MaLP "
            "GROUP BY lp.MaLP, lp.TenLP, lp.SucChua "
            "ORDER BY GiaCaoNhat DESC LIMIT 5"
        )
    if "voucher" in norm or "ma giam gia" in norm:
        return (
            "SELECT Code, LoaiApDung, LoaiGiam, GiaTriGiam, DonHangToiThieu, GiamToiDa, TrangThai "
            "FROM MA_GIAM_GIA ORDER BY GiaTriGiam DESC LIMIT 10"
        )
    if "khu vui choi" in norm or "loai ve" in norm:
        return (
            "SELECT kv.TenKhu, cn.TenCN, lv.TenLoaiVe, lv.GiaVe "
            "FROM KHU_VUI_CHOI kv "
            "JOIN CHI_NHANH cn ON cn.MaCN = kv.MaCN "
            "JOIN LOAI_VE lv ON lv.MaKhu = kv.MaKhu "
            "ORDER BY lv.GiaVe DESC LIMIT 10"
        )
    return None


def _format_vnd(amount: Any) -> str:
    try:
        return f"{int(round(float(amount))):,} VND"
    except (TypeError, ValueError):
        return "0 VND"


def _sanitize_customer_reply(reply: str, audience: str) -> str:
    if audience == "ops":
        return reply
    cleaned = re.sub(r"```[\s\S]*?```", "", reply)
    cleaned = re.sub(r"\b[A-Za-z0-9_/-]+\.md\b", "tài liệu hệ thống", cleaned)
    return cleaned.strip()


def _dispatch_tool(
    tool_name: str,
    args: dict[str, Any],
    user: dict[str, Any] | None,
    default_ma_cn: int | None,
) -> dict[str, Any]:
    if tool_name == "retrieve_knowledge":
        query = str(args.get("query") or "")
        top_k = int(args.get("top_k") or 4)
        audience = "ops" if _resolve_agent_mode(user) == "ops_bi_analyst" else "customer"
        chunks = retrieve_knowledge(query, top_k=max(1, min(6, top_k)), audience=audience)
        return {"chunks": chunks}
    if tool_name == "search_available_rooms":
        return tool_search_available_rooms(
            user,
            ma_cn=args.get("ma_cn") or default_ma_cn,
            branch_keyword=args.get("branch_keyword"),
            ngay_checkin=args.get("ngay_checkin"),
            ngay_checkout=args.get("ngay_checkout"),
            suc_chua=int(args.get("suc_chua") or 2),
            room_type_hint=args.get("room_type_hint"),
            sort_order=str(args.get("sort_order") or "asc"),
        )
    if tool_name == "room_price_rankings":
        return tool_room_price_rankings(
            user,
            ma_cn=args.get("ma_cn"),
            branch_keyword=args.get("branch_keyword"),
            order=str(args.get("order") or "desc"),
            target_date=args.get("target_date"),
        )
    if tool_name == "recommend_vouchers":
        return tool_recommend_vouchers(
            user,
            ngay_checkin=args.get("ngay_checkin"),
            ngay_checkout=args.get("ngay_checkout"),
            has_amusement=bool(args.get("has_amusement", False)),
            estimated_total=float(args.get("estimated_total") or 4000000),
        )
    if tool_name == "get_catalog_highlights":
        return tool_get_catalog_highlights(
            user,
            ma_cn=args.get("ma_cn") or default_ma_cn,
            branch_keyword=args.get("branch_keyword"),
        )
    if tool_name == "get_my_bookings_and_notifications":
        return tool_get_my_bookings_and_notifications(user)
    if tool_name == "bi_branch_analytics":
        return tool_bi_branch_analytics(user, ma_cn=args.get("ma_cn") or default_ma_cn)
    if tool_name == "run_safe_readonly_sql":
        return tool_run_safe_readonly_sql(user, str(args.get("sql_query") or ""))
    raise ValueError(f"Tool '{tool_name}' không được hỗ trợ.")


def _run_local_hybrid_agent(
    user: dict[str, Any] | None,
    message: str,
    history: list[dict[str, str]] | None = None,
    ma_cn: int | None = None,
) -> dict[str, Any]:
    mode = _resolve_agent_mode(user)
    audience = "ops" if mode == "ops_bi_analyst" else "customer"
    decision = classify_intent(message, history=history, explicit_ma_cn=ma_cn)
    slots = decision.slots
    active = decision.active_intents
    norm = strip_accents(message.lower())

    sql_preview: str | None = None
    suggested_action: dict[str, Any] | None = None

    branch_kw: str | None = slots.get("branch_kw")
    region: str | None = slots.get("region")
    room_type_hint: str | None = slots.get("room_type_hint")
    checkin: str | None = slots.get("checkin")
    checkout: str | None = slots.get("checkout")
    capacity: int = int(slots.get("capacity") or 2)
    asks_all_branches: bool = bool(slots.get("asks_all_branches"))

    # If user asked by region (Miền Bắc / Miền Trung / Miền Nam) without specific city
    region_branches: list[dict[str, Any]] = []
    if region and not branch_kw:
        region_branches = resolve_branches_by_region(region)
        if region_branches and "search_rooms" in active:
            branch_kw = region_branches[0]["TenCN"]

    effective_ma_cn = ma_cn
    if effective_ma_cn is None and branch_kw:
        branch_row = resolve_branch(branch_keyword=branch_kw)
        if branch_row:
            effective_ma_cn = int(branch_row["MaCN"])

    # Handle pure greeting / out-of-scope directly without spamming RAG docs
    if decision.primary_intent == "greeting_or_help":
        reply = (
            "Xin chào! Tôi là **Trợ lý AI Aurelia** của hệ thống Khách sạn & Khu vui chơi 3 miền. Tôi có thể hỗ trợ bạn:\n"
            "- Tìm phòng trống theo chi nhánh, ngày lưu trú, số khách & báo giá chi tiết từng đêm\n"
            "- So sánh giá hạng phòng giữa các chi nhánh (cao nhất / thấp nhất)\n"
            "- Tư vấn mã giảm giá (Voucher) ngày thường & ngày lễ\n"
            "- Xem khu vui chơi, vé QR, gói combo và dịch vụ spa/ẩm thực\n"
            "- Giải đáp quy định thanh toán, đặt cọc 30%, hóa đơn, đổi ngày & hủy phòng"
        )
        return {
            "reply": reply,
            "mode": mode,
            "engine": "local_hybrid_rag",
            "citations": [],
            "tool_traces": [{"tool": "intent_router", "args": {"intent": "greeting_or_help"}, "summary": "Nhận diện lời chào / yêu cầu trợ giúp"}],
            "sql_preview": None,
            "suggested_action": None,
        }

    if decision.primary_intent == "out_of_scope":
        reply = (
            "Xin lỗi, tôi là trợ lý chuyên hỗ trợ **đặt phòng khách sạn, vé khu vui chơi, dịch vụ chi nhánh, voucher và quy định lưu trú** của hệ thống Aurelia 3 miền nên chưa hỗ trợ chủ đề ngoài phạm vi này.\n"
            "Bạn có muốn tôi kiểm tra phòng trống, gợi ý ưu đãi hoặc giải đáp chính sách đặt phòng không?"
        )
        return {
            "reply": reply,
            "mode": mode,
            "engine": "local_hybrid_rag",
            "citations": [],
            "tool_traces": [{"tool": "intent_router", "args": {"intent": "out_of_scope"}, "summary": "Từ chối nhẹ nhàng câu hỏi ngoài phạm vi nghiệp vụ"}],
            "sql_preview": None,
            "suggested_action": None,
        }

    # Retrieve RAG knowledge with semantic category preference & no stale branch boost for general policy queries
    is_policy_only = decision.primary_intent == "policy_faq" and not branch_kw and not region
    citations = retrieve_knowledge(
        message,
        top_k=4,
        audience=audience,
        ma_cn=None if (asks_all_branches or is_policy_only) else effective_ma_cn,
        prefer_categories=("policy", "payment", "pricing", "vouchers", "pricing_rules", "branches", "rooms")
        if "policy_faq" in active
        else None,
    )
    tool_traces: list[dict[str, Any]] = [
        {
            "tool": "retrieve_knowledge",
            "args": {"query": message, "intents": sorted(active), "ma_cn": None if (asks_all_branches or is_policy_only) else effective_ma_cn},
            "summary": f"Định tuyến ngữ nghĩa ({', '.join(sorted(active))}) & truy xuất {len(citations)} đoạn tri thức",
        }
    ]

    sections: list[str] = []

    if region_branches and ("policy_faq" in active or "search_rooms" in active) and not slots.get("branch_kw"):
        reg_lines = [f"**Các chi nhánh tại {region} ({len(region_branches)} chi nhánh):**"]
        for rb in region_branches:
            reg_lines.append(f"- **{rb['TenCN']}**: {rb.get('DiaChi', '')} *(SĐT: {rb.get('SDT', '')})*")
        sections.append("\n".join(reg_lines))

    # 1) Admin SQL & BI Analytics
    if "admin_sql" in active or "bi_analytics" in active:
        if mode != "ops_bi_analyst":
            sections.append(
                "**Giới hạn phân quyền RBAC:** Tài khoản hiện tại thuộc nhóm "
                f"`{capabilities_role_label(user)}`, không có quyền truy cập công cụ BI nội bộ hoặc chạy SQL hệ thống. "
                "Tôi vẫn có thể hỗ trợ tìm phòng trống, báo giá ngày lễ, gợi ý voucher và giải đáp chính sách đặt phòng."
            )
            tool_traces.append(
                {"tool": "rbac_guard", "args": {"requested": sorted(active), "mode": mode}, "summary": "Chặn truy cập BI/SQL theo RBAC phía backend"}
            )
        else:
            run_bi = "bi_analytics" in active
            if "admin_sql" in active:
                explicit_sql = slots.get("sql_snippet") or _build_local_nl_sql(message)
                if explicit_sql:
                    if not (user and user.get("is_admin")):
                        sections.append(
                            "**Phân quyền SQL:** Công cụ chạy SQL chỉ mở cho **Admin hệ thống**. "
                            "Dưới đây là số liệu BI tổng hợp trong phạm vi chi nhánh bạn quản lý:"
                        )
                        run_bi = True
                    else:
                        try:
                            sql_res = _dispatch_tool("run_safe_readonly_sql", {"sql_query": explicit_sql}, user, effective_ma_cn)
                            sql_preview = sql_res["executed_sql"]
                            tool_traces.append(
                                {
                                    "tool": "run_safe_readonly_sql",
                                    "args": {"sql_query": sql_preview},
                                    "summary": f"Trả về {sql_res['row_count']} dòng (chỉ đọc an toàn)",
                                }
                            )
                            lines = [f"**Kết quả SQL an toàn ({sql_res['row_count']} dòng):**"]
                            for idx, row in enumerate(sql_res["rows"][:10], start=1):
                                lines.append(f"{idx}. " + ", ".join(f"{k}: {v}" for k, v in row.items()))
                            sections.append("\n".join(lines))
                        except (ValueError, HTTPException) as exc:
                            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
                            sections.append(f"**Từ chối truy vấn SQL:** {detail}")
                else:
                    run_bi = True

            if run_bi:
                try:
                    bi_res = _dispatch_tool("bi_branch_analytics", {"ma_cn": effective_ma_cn}, user, effective_ma_cn)
                    tool_traces.append(
                        {
                            "tool": "bi_branch_analytics",
                            "args": {"ma_cn": effective_ma_cn},
                            "summary": f"Tổng hợp BI cho {len(bi_res['revenue_by_branch'])} chi nhánh",
                        }
                    )
                    lines = ["**Báo cáo BI theo phạm vi phân quyền chi nhánh:**"]
                    for rev in bi_res["revenue_by_branch"]:
                        lines.append(
                            f"- **{rev['TenCN']}** (`CN {rev['MaCN']}`): "
                            f"{int(rev.get('SoHoaDon') or 0)} hóa đơn | "
                            f"Doanh thu: {_format_vnd(rev.get('TongDoanhThu'))} | "
                            f"Đã thu: {_format_vnd(rev.get('TongDaThu'))}"
                        )
                    if bi_res.get("room_occupancy"):
                        lines.append("\n**Công suất phòng hiện tại:**")
                        for occ in bi_res["room_occupancy"]:
                            tong = int(occ.get("TongSoPhong") or occ.get("TongPhong") or 0)
                            trong = int(occ.get("SoPhongTrong") or occ.get("PhongTrong") or 0)
                            pct = float(occ.get("TyLeLapDayPhanTram") or occ.get("TyLeLapDay") or 0)
                            lines.append(f"- {occ.get('TenCN', 'CN')}: trống {trong}/{tong} phòng ({pct:.1f}% lấp đầy)")
                    if bi_res.get("top_services"):
                        lines.append("\n**Top doanh thu dịch vụ:**")
                        for srv in bi_res["top_services"][:5]:
                            lines.append(f"- {srv['TenDV']}: {int(srv.get('TongLuot') or 0)} lượt — {_format_vnd(srv.get('TongDoanhThu'))}")
                    sections.append("\n".join(lines))
                except HTTPException as exc:
                    sections.append(f"**Không thể truy cập BI:** {exc.detail}")

    # 2) My Bookings & Notifications
    if "my_bookings" in active:
        try:
            mine = _dispatch_tool("get_my_bookings_and_notifications", {}, user, effective_ma_cn)
            if mine.get("error") or mine.get("info"):
                sections.append(f"**Lưu ý:** {mine.get('error') or mine.get('info')}")
            else:
                bookings = mine.get("bookings") or []
                notifs = mine.get("notifications") or []
                unread = sum(1 for n in notifs if n.get("TrangThai") == "Chờ xác nhận")
                tool_traces.append(
                    {
                        "tool": "get_my_bookings_and_notifications",
                        "args": {},
                        "summary": f"{len(bookings)} booking, {unread} thông báo chờ xác nhận",
                    }
                )
                lines = [f"**Hồ sơ của {mine['customer_name']}** (Thông báo chờ xác nhận: **{unread}**):"]
                if bookings:
                    lines.append("Booking gần nhất:")
                    for b in bookings[:5]:
                        lines.append(
                            f"- **#{b['MaDP']}** ({b['TenCN']} · Phòng {b['SoPhong']}): {b['NgayCheckIn']} → {b['NgayCheckOut']} "
                            f"| Trạng thái: `{b['TrangThaiDatPhong']}` | Hóa đơn: {_format_vnd(b['TongTienHoaDon'])}"
                        )
                else:
                    lines.append("- Chưa có booking nào.")
                if notifs:
                    lines.append("\nThông báo mới nhất:")
                    for n in notifs[:5]:
                        otp_note = " (cần xác thực OTP)" if n.get("OtpCode") else ""
                        lines.append(f"- **#{n['MaTB']}** [{n['LoaiTB']}] `{n['TrangThai']}`{otp_note}: {n['TieuDe']}")
                sections.append("\n".join(lines))
        except HTTPException as exc:
            sections.append(f"**Lưu ý:** {exc.detail}")

    # 3) Room Price Rankings
    if "price_ranking" in active:
        rank_order = str(slots.get("price_order") or "desc")
        scoped_all = asks_all_branches or not (branch_kw or effective_ma_cn)
        rank_res = _dispatch_tool(
            "room_price_rankings",
            {
                "ma_cn": None if scoped_all else effective_ma_cn,
                "branch_keyword": None if scoped_all else branch_kw,
                "order": rank_order,
                "target_date": checkin,
            },
            user,
            effective_ma_cn,
        )
        items = rank_res.get("items") or []
        tool_traces.append(
            {
                "tool": "room_price_rankings",
                "args": {"order": rank_order, "scope": rank_res.get("branch_scoped")},
                "summary": f"Tổng hợp giá phòng ({len(items)} chi nhánh)",
            }
        )
        label = "giá thấp nhất" if rank_order == "asc" else "giá cao nhất"
        lines = [
            f"**Phòng có {label} tại {rank_res.get('branch_scoped', 'các chi nhánh').lower()}** "
            f"(áp dụng ngày {rank_res.get('target_date')}):"
        ]
        for item in items:
            lines.append(
                f"- **{item['TenCN']}**: Hạng **{item['TenLP']}** ({item['SucChua']} khách · "
                f"Phòng {item['PhongDaiDien']}) — Giá ngày thường/hôm nay: **{_format_vnd(item['GiaNgay'])}/đêm** "
                f"*(cao điểm/lễ tới {_format_vnd(item['GiaCaoNhat'])}/đêm)*"
            )
        sections.append("\n".join(lines))

    # 4) Room Availability Search
    room_res: dict[str, Any] | None = None
    if "search_rooms" in active:
        room_res = _dispatch_tool(
            "search_available_rooms",
            {
                "ma_cn": effective_ma_cn,
                "branch_keyword": branch_kw,
                "ngay_checkin": checkin,
                "ngay_checkout": checkout,
                "suc_chua": capacity,
                "room_type_hint": room_type_hint,
                "sort_order": "desc" if slots.get("price_order") == "desc" and "vip" in norm else "asc",
            },
            user,
            effective_ma_cn,
        )
        branch = room_res["branch"]
        hol = room_res["holiday_info"]
        tool_traces.append(
            {
                "tool": "search_available_rooms",
                "args": {
                    "branch": branch["TenCN"],
                    "checkin": room_res["ngay_checkin"],
                    "checkout": room_res["ngay_checkout"],
                    "suc_chua": room_res["suc_chua"],
                    "room_type_hint": room_type_hint,
                },
                "summary": f"Tìm thấy {room_res['total_available']} phòng trống",
            }
        )
        holiday_label = (
            f"Dịp lễ: {', '.join(hol['holiday_names'])}"
            if hol["is_holiday"]
            else "Ngày thường (không vướng ngày lễ)"
        )
        tier_note = f" · ưu tiên hạng {room_type_hint}" if room_type_hint else ""
        lines = [
            f"**Phòng trống tại {branch['TenCN']}** "
            f"({room_res['ngay_checkin']} → {room_res['ngay_checkout']}, {room_res['nights']} đêm, {room_res['suc_chua']} khách{tier_note}) — *{holiday_label}*:"
        ]
        if room_res["rooms"]:
            for rm in room_res["rooms"][:5]:
                gia_dem = rm.get("GiaMoiDem") or round(float(rm["TongTienKhoangNgay"]) / max(1, int(room_res.get("nights", 1))))
                lines.append(
                    f"- **Phòng {rm['SoPhong']} — {rm['TenLP']}** (sức chứa {rm['SucChua']}): "
                    f"khoảng **{_format_vnd(gia_dem)}/đêm** *(tổng {room_res['nights']} đêm: {_format_vnd(rm['TongTienKhoangNgay'])})*"
                )
            top_rm = room_res["rooms"][0]
            suggested_action = {
                "type": "prefill_booking",
                "label": f"Điền form đặt phòng {branch['TenCN']}",
                "ma_cn": branch["MaCN"],
                "ngay_checkin": room_res["ngay_checkin"],
                "ngay_checkout": room_res["ngay_checkout"],
                "ma_loai": top_rm["MaLP"],
            }
        else:
            lines.append("- Hiện không còn phòng trống phù hợp trong khoảng ngày này.")
        sections.append("\n".join(lines))

    # 5) Voucher Recommendation
    if "voucher_advice" in active:
        est_total = (
            float(room_res["rooms"][0]["TongTienKhoangNgay"])
            if room_res and room_res.get("rooms")
            else 4500000.0
        )
        v_res = _dispatch_tool(
            "recommend_vouchers",
            {
                "ngay_checkin": room_res["ngay_checkin"] if room_res else checkin,
                "ngay_checkout": room_res["ngay_checkout"] if room_res else checkout,
                "has_amusement": bool(slots.get("has_amusement_cue")),
                "estimated_total": est_total,
            },
            user,
            effective_ma_cn,
        )
        tool_traces.append(
            {
                "tool": "recommend_vouchers",
                "args": {"is_holiday": v_res["is_holiday"], "has_amusement": v_res["has_amusement"]},
                "summary": f"Gợi ý {len(v_res.get('recommended', []))} voucher",
            }
        )
        lines = [f"**Tư vấn voucher:**\n- {v_res['rule']}"]
        for rec in v_res.get("recommended", []):
            lines.append(
                f"- Mã **`{rec['Code']}`** ({rec['LoaiApDung']}): "
                f"giảm ước tính **{_format_vnd(rec['UocTinhGiam'])}** (đơn tối thiểu {_format_vnd(rec['DonHangToiThieu'])})"
            )
        if not v_res.get("recommended"):
            lines.append("- Hiện không có mã nào áp dụng được cho kịch bản này.")
        sections.append("\n".join(lines))

    # 6) Catalog Highlights (Theme parks, QR Tickets, Combos, Services)
    if "catalog_highlights" in active:
        cat_res = _dispatch_tool(
            "get_catalog_highlights",
            {"ma_cn": effective_ma_cn, "branch_keyword": branch_kw},
            user,
            effective_ma_cn,
        )
        branch = cat_res["branch"]
        tickets = cat_res.get("tickets") or []
        combos = cat_res.get("combos") or []
        services = cat_res.get("services") or []
        tool_traces.append(
            {
                "tool": "get_catalog_highlights",
                "args": {"branch": branch["TenCN"]},
                "summary": f"{len(tickets)} vé vui chơi, {len(combos)} combo, {len(services)} dịch vụ",
            }
        )
        lines = [f"**Danh mục giải trí & dịch vụ tại {branch['TenCN']}:**"]
        if tickets:
            for tk in tickets[:4]:
                lines.append(
                    f"- **Vé khu vui chơi:** {tk['TenKhu']} — {tk['TenLoaiVe']} ({tk['DoiTuong']}, {_format_vnd(tk['GiaVe'])})"
                )
        if combos:
            for cb in combos[:3]:
                lines.append(f"- **Combo ưu đãi:** {cb['TenCombo']} ({_format_vnd(cb['GiaGoi'])})")
        if services:
            lines.append(
                "- **Dịch vụ tại chi nhánh:** " + "; ".join(f"{s['TenDV']} ({_format_vnd(s['DonGia'])})" for s in services[:5])
            )
        sections.append("\n".join(lines))

    # 7) Policy & Knowledge Citations (score-filtered to prevent irrelevant tail chunks)
    if not sections or "policy_faq" in active:
        if citations:
            ordered = citations
            if "policy_faq" in active:
                pol_sys = [c for c in citations if str(c.get("id", "")).startswith(("policy:", "system:", "db:MA_GIAM_GIA", "db:QUY_DOI"))]
                if pol_sys:
                    ordered = pol_sys
            top_score = float(ordered[0].get("score") or 0.0)
            kept = [
                c
                for idx, c in enumerate(ordered[:2])
                if idx == 0 or float(c.get("score") or 0.0) >= top_score * 0.88
            ]
            sections.append("\n\n".join(f"**{c['title']}**\n{c['snippet']}" for c in kept))
        elif not sections:
            sections.append(
                "Tôi có thể hỗ trợ bạn tìm phòng trống, so sánh giá phòng giữa các chi nhánh, tư vấn voucher ngày thường/ngày lễ, xem dịch vụ khu vui chơi hoặc giải đáp chính sách đặt cọc và hủy phòng."
            )

    reply_text = _sanitize_customer_reply("\n\n".join(sections), audience)
    return {
        "reply": reply_text,
        "mode": mode,
        "engine": "local_hybrid_rag",
        "citations": citations,
        "tool_traces": tool_traces,
        "sql_preview": sql_preview,
        "suggested_action": suggested_action,
    }


def _gemini_tool_declarations(user: dict[str, Any] | None) -> list[dict[str, Any]]:
    allowed = set(_allowed_tool_names(user))
    catalog: dict[str, dict[str, Any]] = {
        "retrieve_knowledge": {
            "name": "retrieve_knowledge",
            "description": "Tìm kiếm tài liệu quy định, chính sách thanh toán, hủy/đổi lịch và thông tin chi nhánh bằng RAG.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Câu truy vấn tìm kiếm tài liệu."},
                    "top_k": {"type": "INTEGER", "description": "Số đoạn trích tối đa (1-6)."},
                },
                "required": ["query"],
            },
        },
        "search_available_rooms": {
            "name": "search_available_rooms",
            "description": "Tra cứu phòng còn trống theo chi nhánh, ngày checkin/checkout, số khách, hạng phòng và kiểm tra phụ thu ngày lễ.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "ma_cn": {"type": "INTEGER", "description": "Mã chi nhánh nếu đã biết."},
                    "branch_keyword": {"type": "STRING", "description": "Tên chi nhánh/thành phố, ví dụ Đà Nẵng, Phú Quốc."},
                    "ngay_checkin": {"type": "STRING", "description": "Ngày nhận phòng YYYY-MM-DD."},
                    "ngay_checkout": {"type": "STRING", "description": "Ngày trả phòng YYYY-MM-DD."},
                    "suc_chua": {"type": "INTEGER", "description": "Số lượng khách."},
                    "room_type_hint": {"type": "STRING", "description": "Hạng phòng ưu tiên (Standard, Superior, Deluxe, Family, Suite, Presidential Suite)."},
                },
            },
        },
        "room_price_rankings": {
            "name": "room_price_rankings",
            "description": "Tìm phòng / hạng phòng có giá cao nhất hoặc thấp nhất của từng chi nhánh hoặc 1 chi nhánh cụ thể.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "ma_cn": {"type": "INTEGER", "description": "Để trống nếu hỏi tất cả các chi nhánh."},
                    "branch_keyword": {"type": "STRING"},
                    "order": {"type": "STRING", "description": "'desc' (đắt nhất) hoặc 'asc' (rẻ nhất)."},
                    "target_date": {"type": "STRING", "description": "Ngày cần tham khảo giá YYYY-MM-DD."},
                },
            },
        },
        "recommend_vouchers": {
            "name": "recommend_vouchers",
            "description": "Đề xuất tối ưu 0, 1 hoặc 2 voucher hợp lệ theo ngày lễ/ngày thường và phạm vi khách sạn/khu vui chơi.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "ngay_checkin": {"type": "STRING", "description": "Ngày checkin YYYY-MM-DD."},
                    "ngay_checkout": {"type": "STRING", "description": "Ngày checkout YYYY-MM-DD."},
                    "has_amusement": {"type": "BOOLEAN", "description": "Có đặt kèm vé khu vui chơi không."},
                    "estimated_total": {"type": "NUMBER", "description": "Tổng tiền dự kiến (VND)."},
                },
            },
        },
        "get_catalog_highlights": {
            "name": "get_catalog_highlights",
            "description": "Lấy danh sách khu vui chơi, loại vé, combo và dịch vụ tại chi nhánh.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "ma_cn": {"type": "INTEGER"},
                    "branch_keyword": {"type": "STRING"},
                },
            },
        },
        "get_my_bookings_and_notifications": {
            "name": "get_my_bookings_and_notifications",
            "description": "Xem danh sách booking và thông báo xác nhận OTP/dịch vụ của chính khách hàng đang đăng nhập.",
            "parameters": {"type": "OBJECT", "properties": {}},
        },
        "bi_branch_analytics": {
            "name": "bi_branch_analytics",
            "description": "Tổng hợp doanh thu, công suất phòng và dịch vụ trong phạm vi chi nhánh mà nhân viên/quản lý/admin được cấp quyền.",
            "parameters": {
                "type": "OBJECT",
                "properties": {"ma_cn": {"type": "INTEGER"}},
            },
        },
        "run_safe_readonly_sql": {
            "name": "run_safe_readonly_sql",
            "description": "Chỉ dành cho Admin hệ thống: chạy truy vấn SELECT/WITH chỉ đọc an toàn trên các bảng nghiệp vụ (tối đa 30 dòng).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "sql_query": {"type": "STRING", "description": "Câu lệnh SELECT hoặc WITH hợp lệ."},
                },
                "required": ["sql_query"],
            },
        },
    }
    return [decl for name, decl in catalog.items() if name in allowed]


def _run_gemini_agent(
    user: dict[str, Any] | None,
    message: str,
    history: list[dict[str, str]] | None,
    ma_cn: int | None,
) -> dict[str, Any]:
    settings = get_settings()
    mode = _resolve_agent_mode(user)
    audience = "ops" if mode == "ops_bi_analyst" else "customer"
    decision = classify_intent(message, history=history, explicit_ma_cn=ma_cn)
    slots = decision.slots
    branch_kw = slots.get("branch_kw")
    effective_ma_cn = ma_cn
    if effective_ma_cn is None and branch_kw:
        branch_row = resolve_branch(branch_keyword=branch_kw)
        if branch_row:
            effective_ma_cn = int(branch_row["MaCN"])

    if decision.primary_intent in ("greeting_or_help", "out_of_scope") or (
        mode != "ops_bi_analyst" and ("bi_analytics" in decision.active_intents or "admin_sql" in decision.active_intents)
    ):
        return _run_local_hybrid_agent(user, message, history=history, ma_cn=ma_cn)

    is_policy_only = decision.primary_intent == "policy_faq" and not branch_kw and not slots.get("region")
    rag_query = f"{message} {branch_kw}".strip() if (slots.get("refers_prior_place") and branch_kw) else message
    baseline_citations = retrieve_knowledge(
        rag_query,
        top_k=5,
        audience=audience,
        ma_cn=None if (slots.get("asks_all_branches") or is_policy_only) else effective_ma_cn,
        prefer_categories=("policy", "payment", "pricing", "vouchers", "pricing_rules", "branches", "rooms")
        if "policy_faq" in decision.active_intents
        else None,
    )
    rag_context = "\n".join(f"- {c['title']}: {c['snippet']}" for c in baseline_citations)
    system_prompt = (
        "Bạn là Trợ lý AI của hệ thống Quản lý Chuỗi Khách sạn & Khu vui chơi 3 miền (Aurelia). "
        "Hãy trả lời ngắn gọn, thân thiện, rõ ràng bằng tiếng Việt tự nhiên.\n"
        "NGUYÊN TẮC BẮT BUỘC:\n"
        "1. CHỈ trả lời dựa trên thông tin nghiệp vụ bên dưới và kết quả JSON thực tế do công cụ trả về.\n"
        "2. Tuyệt đối KHÔNG tự suy đoán hay bịa thêm các kênh/tính năng không tồn tại trên hệ thống (hệ thống CHỈ chạy trên website: KHÔNG gửi email xác nhận tự động, KHÔNG có app di động, KHÔNG tự xuất hóa đơn đỏ VAT điện tử online, KHÔNG có giờ hủy tự động 22:00); nếu thiếu chi tiết hãy nói rõ và hướng dẫn liên hệ Lễ tân chi nhánh.\n"
        "3. Khi báo phòng trống, luôn nêu rõ giá mỗi đêm (GiaMoiDem) kèm tổng tiền toàn kỳ (TongTienKhoangNgay) và số đêm (nights).\n"
        "4. TUYỆT ĐỐI KHÔNG nhắc tên tệp mã nguồn, sơ đồ ERD, câu lệnh SQL, thuật ngữ kỹ thuật lập trình hoặc cấu trúc database khi trả lời khách hàng.\n"
        "5. Nếu câu hỏi nằm ngoài phạm vi đặt phòng/dịch vụ/quy định của khách sạn, hãy từ chối lịch sự.\n"
        f"Vai trò hiện tại: {capabilities_role_label(user)} (mode={mode}, branch_ids={(user or {}).get('branch_ids', [])}).\n\n"
        f"Tài liệu nghiệp vụ liên quan:\n{rag_context}"
    )

    contents: list[dict[str, Any]] = []
    for item in (history or [])[-6:]:
        role = "model" if item.get("role") == "assistant" else "user"
        text = str(item.get("content") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    needs_live_tools = bool(decision.active_intents - {"policy_faq"})
    tools_payload = [{"functionDeclarations": _gemini_tool_declarations(user)}] if needs_live_tools else None

    tool_traces: list[dict[str, Any]] = [
        {
            "tool": "retrieve_knowledge",
            "args": {"query": message, "top_k": 5},
            "summary": f"Truy xuất {len(baseline_citations)} đoạn tri thức RAG nền",
        }
    ]
    all_citations = list(baseline_citations)
    sql_preview: str | None = None
    suggested_action: dict[str, Any] | None = None
    final_text = ""

    with httpx.Client(timeout=25.0) as client:
        for _ in range(5):
            req_body: dict[str, Any] = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.2},
            }
            if tools_payload:
                req_body["tools"] = tools_payload

            resp = client.post(url, json=req_body)
            if resp.status_code in (429, 502, 503, 504):
                time.sleep(1.2)
                resp = client.post(url, json=req_body)
            resp.raise_for_status()
            payload = resp.json()
            candidates = payload.get("candidates") or []
            if not candidates:
                break
            model_content = candidates[0].get("content") or {}
            parts = model_content.get("parts") or []
            contents.append({"role": "model", "parts": parts})

            function_calls = [p["functionCall"] for p in parts if "functionCall" in p]
            text_parts = [p["text"] for p in parts if "text" in p]
            if not function_calls:
                final_text = "\n".join(text_parts).strip()
                break

            fn_responses: list[dict[str, Any]] = []
            for fc in function_calls:
                name = fc.get("name", "")
                args = fc.get("args") or {}
                try:
                    result = _dispatch_tool(name, args, user, ma_cn)
                    if name == "retrieve_knowledge":
                        for chunk in result.get("chunks", []):
                            if all(existing["id"] != chunk["id"] for existing in all_citations):
                                all_citations.append(chunk)
                    if name == "run_safe_readonly_sql" and result.get("executed_sql"):
                        sql_preview = result["executed_sql"]
                    if name == "search_available_rooms" and result.get("rooms"):
                        top_rm = result["rooms"][0]
                        suggested_action = {
                            "type": "prefill_booking",
                            "label": f"Điền form đặt phòng {result['branch']['TenCN']}",
                            "ma_cn": result["branch"]["MaCN"],
                            "ngay_checkin": result["ngay_checkin"],
                            "ngay_checkout": result["ngay_checkout"],
                            "ma_loai": top_rm["MaLP"],
                        }
                    tool_traces.append({"tool": name, "args": args, "summary": "Thực thi thành công"})
                    fn_responses.append({"functionResponse": {"name": name, "response": {"result": result}}})
                except (HTTPException, ValueError) as exc:
                    err_msg = exc.detail if isinstance(exc, HTTPException) else str(exc)
                    tool_traces.append({"tool": name, "args": args, "summary": f"Bị từ chối: {err_msg}"})
                    fn_responses.append({"functionResponse": {"name": name, "response": {"error": err_msg}}})
            contents.append({"role": "user", "parts": fn_responses})

    if not final_text:
        return _run_local_hybrid_agent(user, message, history=history, ma_cn=ma_cn)

    return {
        "reply": _sanitize_customer_reply(final_text, audience),
        "mode": mode,
        "engine": "gemini_rag_agent",
        "citations": all_citations[:5],
        "tool_traces": tool_traces,
        "sql_preview": sql_preview,
        "suggested_action": suggested_action,
    }


def run_ai_agent(
    user: dict[str, Any] | None,
    message: str,
    history: list[dict[str, str]] | None = None,
    ma_cn: int | None = None,
) -> dict[str, Any]:
    clean_message = (message or "").strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail="Vui lòng nhập nội dung câu hỏi cho Trợ lý AI.")

    settings = get_settings()
    if settings.gemini_api_key:
        try:
            return _run_gemini_agent(user, clean_message, history, ma_cn)
        except Exception:
            fallback = _run_local_hybrid_agent(user, clean_message, history=history, ma_cn=ma_cn)
            fallback["tool_traces"].append(
                {
                    "tool": "gemini_fallback",
                    "args": {},
                    "summary": "Gemini API tạm gián đoạn, chuyển sang Local Hybrid RAG",
                }
            )
            return fallback

    return _run_local_hybrid_agent(user, clean_message, history=history, ma_cn=ma_cn)
