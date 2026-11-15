import { statusBadgeClass } from "../utils/format";

export default function Badge({ status }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusBadgeClass(
        status
      )}`}
    >
      {status}
    </span>
  );
}
