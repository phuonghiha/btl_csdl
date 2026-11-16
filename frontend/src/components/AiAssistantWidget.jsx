import { useEffect, useRef, useState } from "react";
import {
  Bot,
  Send,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { apiFetch } from "../api/client";

const CHAT_STORAGE_PREFIX = "aurelia_ai_chat";
const MAX_CACHED_MESSAGES = 60;

function getChatStorageKey(userId) {
  return userId ? `${CHAT_STORAGE_PREFIX}:user:${userId}` : `${CHAT_STORAGE_PREFIX}:guest`;
}

function readCachedMessages(userId) {
  try {
    const raw = localStorage.getItem(getChatStorageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeCachedMessages(userId, list) {
  try {
    const safeList = Array.isArray(list) ? list.slice(-MAX_CACHED_MESSAGES) : [];
    localStorage.setItem(getChatStorageKey(userId), JSON.stringify(safeList));
  } catch {
    // ignore storage quota errors
  }
}

function clearCachedMessages(userId) {
  try {
    localStorage.removeItem(getChatStorageKey(userId));
  } catch {
    // ignore storage errors
  }
}

const MODE_META = {
  ops_bi_analyst: {
    label: "Ops & BI Analyst",
    badgeClass: "bg-indigo-100 text-indigo-800 border-indigo-200",
    hint: "Truy vấn BI chi nhánh theo phân quyền & kiểm tra quy định nghiệp vụ",
  },
  customer_concierge: {
    label: "Concierge Khách hàng",
    badgeClass: "bg-emerald-100 text-emerald-800 border-emerald-200",
    hint: "Tìm phòng, gợi ý voucher hợp lệ, xem booking & thông báo OTP của bạn",
  },
  public_concierge: {
    label: "Tư vấn Đặt phòng",
    badgeClass: "bg-amber-100 text-amber-800 border-amber-200",
    hint: "Tư vấn phòng trống, giá ngày lễ, voucher & quy định hệ thống",
  },
};

function renderFormattedText(text) {
  if (!text) return null;
  const parts = String(text).split(/(\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={idx} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return (
        <em key={idx} className="italic text-stone-600">
          {part.slice(1, -1)}
        </em>
      );
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={idx} className="font-mono text-[11px] px-1 py-0.5 rounded bg-stone-100 text-stone-900">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

export default function AiAssistantWidget({ user, onApplyBookingSuggestion }) {
  const userId = user?.MaTK ?? null;
  const activeUserIdRef = useRef(userId);
  activeUserIdRef.current = userId;

  const [open, setOpen] = useState(false);
  const [capabilities, setCapabilities] = useState(null);
  const [messages, setMessages] = useState(() => readCachedMessages(userId));
  const [historyLoading, setHistoryLoading] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const scrollRef = useRef(null);

  useEffect(() => {
    let active = true;
    apiFetch("/api/ai/capabilities")
      .then((res) => {
        if (active) setCapabilities(res);
      })
      .catch(() => {
        if (active) setCapabilities(null);
      });
    return () => {
      active = false;
    };
  }, [userId]);

  useEffect(() => {
    let active = true;
    const cached = readCachedMessages(userId);
    setMessages(cached);
    setError("");

    if (!userId) {
      setHistoryLoading(false);
      return () => {
        active = false;
      };
    }

    setHistoryLoading(true);
    apiFetch("/api/ai/history")
      .then((res) => {
        if (!active || activeUserIdRef.current !== userId) return;
        const serverItems = Array.isArray(res?.items) ? res.items : [];
        setMessages(serverItems);
        writeCachedMessages(userId, serverItems);
      })
      .catch(() => {
        // Keep optimistic local cache if server history fetch fails transiently
      })
      .finally(() => {
        if (active) setHistoryLoading(false);
      });

    return () => {
      active = false;
    };
  }, [userId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, open, loading]);

  const modeKey = capabilities?.mode || (user ? (user.MaKH ? "customer_concierge" : "ops_bi_analyst") : "public_concierge");
  const modeMeta = MODE_META[modeKey] || MODE_META.public_concierge;

  async function handleClearHistory() {
    const targetUserId = userId;
    setError("");
    clearCachedMessages(targetUserId);
    setMessages([]);
    if (targetUserId) {
      try {
        await apiFetch("/api/ai/history", { method: "DELETE" });
      } catch {
        // ignore transient errors
      }
    }
  }

  async function sendQuestion(questionText) {
    const clean = (questionText ?? input).trim();
    if (!clean || loading) return;

    const targetUserId = userId;
    setError("");
    const userMsg = { role: "user", content: clean };
    const nextHistory = [...messages, userMsg];
    setMessages(nextHistory);
    setInput("");
    setLoading(true);

    try {
      const historyPayload = messages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const res = await apiFetch("/api/ai/chat", {
        method: "POST",
        body: JSON.stringify({
          message: clean,
          history: historyPayload,
        }),
      });
      const assistantMsg = {
        role: "assistant",
        content: res.reply,
        mode: res.mode,
        engine: res.engine,
        citations: res.citations || [],
        tool_traces: res.tool_traces || [],
        sql_preview: res.sql_preview || null,
        suggested_action: res.suggested_action || null,
      };
      const updatedMessages = [...nextHistory, assistantMsg];
      writeCachedMessages(targetUserId, updatedMessages);
      if (activeUserIdRef.current === targetUserId) {
        setMessages(updatedMessages);
      }
    } catch (err) {
      setError(err.message || "Không thể kết nối Trợ lý AI.");
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    sendQuestion();
  }

  return (
    <div className="fixed bottom-5 right-5 z-40">
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="group inline-flex items-center gap-2.5 rounded-full bg-stone-900 hover:bg-stone-800 text-white px-4 py-3 shadow-lg border border-amber-500/40 transition-all"
          title="Mở Trợ lý AI Aurelia"
        >
          <span className="w-8 h-8 rounded-full bg-amber-500 text-stone-950 flex items-center justify-center shadow-xs">
            <Sparkles className="w-4 h-4" />
          </span>
          <div className="text-left pr-1">
            <div className="text-xs font-bold leading-tight">Trợ lý Aurelia</div>
            <div className="text-[10px] text-amber-300 leading-tight">{modeMeta.label}</div>
          </div>
        </button>
      ) : (
        <div className="w-[390px] max-w-[calc(100vw-2rem)] h-[560px] max-h-[calc(100vh-3rem)] rounded-2xl bg-white border border-stone-200 shadow-2xl flex flex-col overflow-hidden">
          {/* Header */}
          <div className="bg-stone-900 text-white px-4 py-3 flex items-start justify-between gap-2">
            <div className="flex items-start gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-amber-500 text-stone-950 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-bold">Aurelia AI Agent</span>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${modeMeta.badgeClass}`}
                  >
                    {modeMeta.label}
                  </span>
                </div>
                <div className="text-[11px] text-stone-300 mt-0.5 flex items-center gap-1.5">
                  <ShieldCheck className="w-3 h-3 text-emerald-400 shrink-0" />
                  <span>
                    {modeKey === "ops_bi_analyst"
                      ? "Trợ lý vận hành & BI theo phân quyền"
                      : "Trợ lý tư vấn đặt phòng & dịch vụ"}
                  </span>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button
                  type="button"
                  onClick={handleClearHistory}
                  className="p-1.5 rounded-lg text-stone-300 hover:text-white hover:bg-stone-800"
                  title="Xóa hội thoại"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg text-stone-300 hover:text-white hover:bg-stone-800"
                title="Thu gọn"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-3.5 space-y-3 bg-stone-50">
            {historyLoading && messages.length === 0 ? (
              <div className="rounded-xl bg-white border border-stone-200 p-3 text-xs text-stone-500">
                Đang khôi phục lịch sử hội thoại...
              </div>
            ) : messages.length === 0 ? (
              <div className="space-y-3">
                <div className="rounded-xl bg-white border border-stone-200 p-3 text-xs text-stone-700 leading-relaxed">
                  <div className="font-semibold text-stone-900 mb-1">Xin chào!</div>
                  <p>{modeMeta.hint}.</p>
                  <p className="text-[11px] text-stone-500 mt-1">
                    Mọi truy vấn dữ liệu đều được lọc theo phân quyền RBAC trên server.
                  </p>
                </div>

                {capabilities?.sample_prompts?.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-[11px] font-semibold text-stone-500 uppercase tracking-wide px-1">
                      Gợi ý câu hỏi nhanh
                    </div>
                    {capabilities.sample_prompts.map((prompt, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => sendQuestion(prompt)}
                        className="w-full text-left text-xs rounded-xl bg-white hover:bg-amber-50 border border-stone-200 hover:border-amber-300 px-3 py-2 text-stone-700 transition-colors"
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[90%] rounded-2xl px-3.5 py-2.5 text-xs leading-relaxed whitespace-pre-wrap ${
                      msg.role === "user"
                        ? "bg-stone-900 text-white rounded-br-sm"
                        : "bg-white border border-stone-200 text-stone-800 rounded-bl-sm shadow-2xs"
                    }`}
                  >
                    <div>{msg.role === "assistant" ? renderFormattedText(msg.content) : msg.content}</div>

                    {msg.suggested_action?.type === "prefill_booking" && onApplyBookingSuggestion && (
                      <button
                        type="button"
                        onClick={() => {
                          onApplyBookingSuggestion(msg.suggested_action);
                          setOpen(false);
                        }}
                        className="mt-2.5 w-full inline-flex items-center justify-center gap-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-stone-950 font-semibold px-3 py-1.5 text-xs transition-colors"
                      >
                        <Sparkles className="w-3.5 h-3.5" />
                        {msg.suggested_action.label || "Áp dụng vào form đặt phòng"}
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}

            {loading && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm bg-white border border-stone-200 px-3.5 py-2.5 text-xs text-stone-500">
                  Đang tìm thông tin phù hợp...
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-xl bg-rose-50 border border-rose-200 px-3 py-2 text-xs text-rose-700">
                {error}
              </div>
            )}
          </div>

          {/* Input */}
          <form onSubmit={handleSubmit} className="p-3 bg-white border-t border-stone-200 flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={
                modeKey === "ops_bi_analyst"
                  ? "Hỏi về doanh thu, công suất phòng, quy định..."
                  : "Hỏi về phòng trống, giá phòng, voucher, dịch vụ..."
              }
              className="flex-1 rounded-xl border border-stone-300 px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-amber-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="inline-flex items-center justify-center rounded-xl bg-stone-900 hover:bg-stone-800 disabled:opacity-40 text-white p-2.5 transition-colors"
              title="Gửi câu hỏi"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
