"use client";

const STATUS_STYLES: Record<string, string> = {
  approved: "bg-green-100 text-green-800",
  approved_auto: "bg-green-100 text-green-800",
  needs_review: "bg-yellow-100 text-yellow-800",
  pending: "bg-yellow-100 text-yellow-800",
  rejected: "bg-red-100 text-red-800",
  rejected_auto: "bg-red-100 text-red-800",
};

export default function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || "bg-gray-100 text-gray-800";
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${style}`}
    >
      {status.replace(/_/g, " ")}
    </span>
  );
}
