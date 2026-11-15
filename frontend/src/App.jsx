import { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  BedDouble,
  Bell,
  Building2,
  KeyRound,
  LogOut,
  QrCode,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { apiFetch, getStoredToken, setStoredToken } from "./api/client";
import LoginModal from "./components/LoginModal";
import NotificationModal from "./components/NotificationModal";
import PaymentQrModal from "./components/PaymentQrModal";
import ProfileModal from "./components/ProfileModal";
import AdminDashboardPage from "./pages/AdminDashboardPage";
import BookingPortalPage from "./pages/BookingPortalPage";
import FrontDeskPage from "./pages/FrontDeskPage";
import TicketScannerPage from "./pages/TicketScannerPage";

const TABS = [
  {
    id: "booking",
    label: "Đặt phòng & Khách hàng",
    icon: Sparkles,
    requiredPerms: null, // Public
  },
  {
    id: "frontdesk",
    label: "Bàn Lễ tân",
    icon: BedDouble,
    requiredPerms: ["ROOM.READ_BRANCH", "BOOKING.READ_BRANCH"],
  },
  {
    id: "scanner",
    label: "Soát vé QR & Dịch vụ",
    icon: QrCode,
    requiredPerms: null, // Public catalog + auth ticket scan
  },
  {
    id: "admin",
    label: "Quản trị & Báo cáo",
    icon: BarChart3,
    requiredPerms: ["REPORT.READ_BRANCH", "BOOKING.READ_BRANCH"],
  },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("booking");
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifLoading, setNotifLoading] = useState(false);
  const [notifQrTarget, setNotifQrTarget] = useState({ maHd: null, initialQr: null });

  const loadNotifications = useCallback(async () => {
    if (!user?.MaKH) {
      setNotifications([]);
      setUnreadCount(0);
      return;
    }
    setNotifLoading(true);
    try {
      const data = await apiFetch("/api/notifications");
      setNotifications(Array.isArray(data?.items) ? data.items : []);
      setUnreadCount(Number(data?.unread_count || 0));
    } catch {
      // ignore transient polling error
    } finally {
      setNotifLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (!user?.MaKH) {
      setNotifications([]);
      setUnreadCount(0);
      return;
    }
    loadNotifications();
    const timer = setInterval(loadNotifications, 5000);
    return () => clearInterval(timer);
  }, [user, loadNotifications]);

  useEffect(() => {
    function handleExpired() {
      setUser(null);
      setActiveTab("booking");
      setLoginOpen(true);
    }
    window.addEventListener("auth:expired", handleExpired);
    return () => window.removeEventListener("auth:expired", handleExpired);
  }, []);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setAuthReady(true);
      return;
    }
    apiFetch("/api/auth/me")
      .then((me) => setUser(me))
      .catch(() => setStoredToken(""))
      .finally(() => setAuthReady(true));
  }, []);

  function handleLoginSuccess(loggedInUser) {
    setUser(loggedInUser);
    const perms = loggedInUser?.permissions || [];
    if (loggedInUser?.is_admin || perms.includes("REPORT.READ_BRANCH")) {
      setActiveTab("admin");
    } else if (perms.includes("ROOM.READ_BRANCH")) {
      setActiveTab("frontdesk");
    } else if (perms.includes("SERVICE.RECORD_USE")) {
      setActiveTab("scanner");
    } else {
      setActiveTab("booking");
    }
  }

  function handleLogout() {
    setStoredToken("");
    setUser(null);
    setActiveTab("booking");
  }

  const userPerms = user?.permissions || [];

  return (
    <div className="min-h-screen bg-stone-100 text-stone-900 flex flex-col">
      {/* Top Navbar */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-xs border-b border-stone-200 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-xl bg-stone-900 text-amber-400 flex items-center justify-center shadow-xs">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <p className="font-bold text-stone-900 leading-tight">Aurelia Hotel Chain</p>
                <p className="text-[11px] text-stone-500">Hệ thống quản lý chuỗi 10 khách sạn</p>
              </div>
            </div>

            <div className="lg:hidden">
              {user ? (
                <button
                  onClick={handleLogout}
                  className="inline-flex items-center gap-1 rounded-lg border border-stone-300 px-2.5 py-1.5 text-xs font-medium"
                >
                  <LogOut className="w-3.5 h-3.5" /> Thoát
                </button>
              ) : (
                <button
                  onClick={() => setLoginOpen(true)}
                  className="inline-flex items-center gap-1 rounded-lg bg-stone-900 text-white px-3 py-1.5 text-xs font-medium"
                >
                  <KeyRound className="w-3.5 h-3.5 text-amber-400" /> Đăng nhập
                </button>
              )}
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex flex-wrap items-center gap-1.5">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isAllowed =
                !tab.requiredPerms || tab.requiredPerms.some((p) => userPerms.includes(p));
              const isActive = activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    if (!isAllowed && !user) {
                      setLoginOpen(true);
                      return;
                    }
                    setActiveTab(tab.id);
                  }}
                  className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold transition-colors ${isActive
                    ? "bg-stone-900 text-white shadow-xs"
                    : isAllowed
                      ? "text-stone-700 hover:bg-stone-100"
                      : "text-stone-400 hover:bg-stone-100"
                    }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? "text-amber-400" : ""}`} />
                  {tab.label}
                </button>
              );
            })}
          </nav>

          {/* User Info / Auth Actions */}
          <div className="flex items-center gap-2.5">
            {user?.MaKH && (
              <button
                type="button"
                onClick={() => {
                  setNotifOpen(true);
                  loadNotifications();
                }}
                className="relative inline-flex items-center gap-1.5 px-3 py-2 rounded-xl border border-amber-200 bg-amber-50 hover:bg-amber-100 text-xs font-semibold text-amber-900 transition-colors"
                title="Thông báo OTP & xác nhận dịch vụ"
              >
                <Bell className="w-4 h-4 text-amber-700" />
                <span className="hidden sm:inline">Thông báo</span>
                {unreadCount > 0 && (
                  <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-rose-600 text-white text-[10px] font-bold">
                    {unreadCount}
                  </span>
                )}
              </button>
            )}
            <div className="hidden lg:flex items-center gap-3">
              {user ? (
                <div className="flex items-center gap-2.5">
                  <button
                    onClick={() => setProfileOpen(true)}
                    className="text-right hover:bg-stone-100 px-2 py-1 rounded-lg transition-colors"
                    title="Xem & cập nhật hồ sơ cá nhân"
                  >
                    <p className="text-xs font-bold text-stone-900 flex items-center justify-end gap-1">
                      <UserCheck className="w-3.5 h-3.5 text-emerald-600" />
                      {user.TenNhanVien || user.TenKhachHang || user.TenDangNhap}
                    </p>
                    <p className="text-[11px] text-stone-500">
                      {(user.role_names || []).join(", ") || "Tài khoản"}
                      {user.is_admin
                        ? " · Toàn hệ thống"
                        : user.branch_ids?.length
                          ? ` · CN #${user.branch_ids.join(", #")}`
                          : ""}
                    </p>
                  </button>
                  <button
                    onClick={() => setLoginOpen(true)}
                    className="px-2.5 py-1.5 rounded-lg border border-stone-300 hover:bg-stone-100 text-xs font-medium text-stone-700"
                    title="Đổi tài khoản demo"
                  >
                    Đổi TK
                  </button>
                  <button
                    onClick={handleLogout}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-rose-200 bg-rose-50 hover:bg-rose-100 text-xs font-medium text-rose-700"
                  >
                    <LogOut className="w-3.5 h-3.5" /> Đăng xuất
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setLoginOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-stone-900 hover:bg-stone-800 text-white px-4 py-2 text-xs font-semibold shadow-xs"
                >
                  <KeyRound className="w-4 h-4 text-amber-400" />
                  Đăng nhập / Đổi vai trò
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {!authReady ? (
          <div className="py-16 text-center text-sm text-stone-500">Đang khởi tạo phiên làm việc...</div>
        ) : (
          <>
            {activeTab === "booking" && (
              <BookingPortalPage user={user} onRequireLogin={() => setLoginOpen(true)} />
            )}
            {activeTab === "frontdesk" && <FrontDeskPage user={user} />}
            {activeTab === "scanner" && (
              <TicketScannerPage user={user} onRequireLogin={() => setLoginOpen(true)} />
            )}
            {activeTab === "admin" && <AdminDashboardPage user={user} />}
          </>
        )}
      </main>

      <footer className="border-t border-stone-200 bg-white py-4 text-center text-xs text-stone-500">
        Aurelia Hotel Chain Management · FastAPI + PyMySQL + React (Vite + Tailwind CSS) · MySQL 8.0
      </footer>

      <LoginModal open={loginOpen} onClose={() => setLoginOpen(false)} onSuccess={handleLoginSuccess} />
      <ProfileModal
        open={profileOpen}
        onClose={() => setProfileOpen(false)}
        onProfileUpdated={(updated) => setUser(updated)}
      />
      <NotificationModal
        open={notifOpen}
        notifications={notifications}
        loading={notifLoading}
        onClose={() => setNotifOpen(false)}
        onRefresh={loadNotifications}
        onOpenPaymentQr={(maHd, initialQr) => {
          setNotifOpen(false);
          setNotifQrTarget({ maHd, initialQr });
        }}
      />
      <PaymentQrModal
        maHd={notifQrTarget.maHd}
        initialQr={notifQrTarget.initialQr}
        onClose={() => setNotifQrTarget({ maHd: null, initialQr: null })}
        onPaid={() => {
          loadNotifications();
        }}
      />
    </div>
  );
}
