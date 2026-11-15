export function formatVND(value) {
  const num = Number(value || 0);
  return new Intl.NumberFormat("vi-VN", {
    style: "currency",
    currency: "VND",
    maximumFractionDigits: 0,
  }).format(num);
}

export function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export function formatDateTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    hour12: false,
  });
}

const STATUS_CLASSES = {
  "Trống": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Đã sẵn sàng": "bg-sky-50 text-sky-700 border-sky-200",
  "Đang sử dụng": "bg-amber-50 text-amber-800 border-amber-200",
  "Bảo trì": "bg-rose-50 text-rose-700 border-rose-200",
  "Chờ xác nhận": "bg-amber-50 text-amber-800 border-amber-200",
  "Đã xác nhận": "bg-sky-50 text-sky-700 border-sky-200",
  "Đang lưu trú": "bg-indigo-50 text-indigo-700 border-indigo-200",
  "Đã trả phòng": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Đã hủy": "bg-stone-100 text-stone-600 border-stone-300",
  "Đã thanh toán": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Thanh toán một phần": "bg-amber-50 text-amber-800 border-amber-200",
  "Chưa thanh toán": "bg-rose-50 text-rose-700 border-rose-200",
  "Đã sử dụng": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Chưa sử dụng": "bg-sky-50 text-sky-700 border-sky-200",
  "Hết hạn": "bg-stone-100 text-stone-600 border-stone-300",
  "Hoạt động": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Bị khóa": "bg-rose-50 text-rose-700 border-rose-200",
  "Còn phục vụ": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "Tạm ngưng": "bg-stone-100 text-stone-600 border-stone-300",
};

export function statusBadgeClass(status) {
  return (
    STATUS_CLASSES[status] ||
    "bg-stone-100 text-stone-700 border-stone-200"
  );
}

export function downloadCSV(filename, headers, rows) {
  const escape = (val) => {
    const s = String(val ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.map(escape).join(",")];
  for (const row of rows) {
    lines.push(row.map(escape).join(","));
  }
  const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
