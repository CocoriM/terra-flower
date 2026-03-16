"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import {
  fetchPendingUploads,
  approveUpload,
  rejectUpload,
} from "@/lib/api";
import Navbar from "@/components/Navbar";
import StatusBadge from "@/components/StatusBadge";

interface PendingUpload {
  id: string;
  plant_common_name: string;
  plant_scientific_name: string;
  thumbnail_url: string;
  image_url: string;
  ai_predicted_name: string | null;
  ai_confidence: number | null;
  ai_status: string;
}

export default function ModerationPage() {
  const user = useStore((s) => s.user);
  const router = useRouter();
  const [uploads, setUploads] = useState<PendingUpload[]>([]);
  const [loading, setLoading] = useState(true);
  const [rejectReasons, setRejectReasons] = useState<Record<string, string>>(
    {}
  );
  const [showRejectInput, setShowRejectInput] = useState<string | null>(null);

  useEffect(() => {
    if (!user || (user.role !== "moderator" && user.role !== "admin")) {
      router.push("/");
      return;
    }
    fetchPendingUploads()
      .then((data) => setUploads(data.uploads || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user, router]);

  const handleApprove = async (id: string) => {
    try {
      await approveUpload(id);
      setUploads((prev) => prev.filter((u) => u.id !== id));
    } catch {
      // approve failed
    }
  };

  const handleReject = async (id: string) => {
    const reason = rejectReasons[id];
    if (!reason) return;
    try {
      await rejectUpload(id, reason);
      setUploads((prev) => prev.filter((u) => u.id !== id));
      setShowRejectInput(null);
    } catch {
      // reject failed
    }
  };

  if (!user || (user.role !== "moderator" && user.role !== "admin"))
    return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto pt-20 px-4">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">
          Moderation Dashboard
        </h1>

        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : uploads.length === 0 ? (
          <div className="bg-white rounded-xl shadow-lg p-8 text-center text-gray-500">
            All caught up! No uploads pending review.
          </div>
        ) : (
          <div className="space-y-4">
            {uploads.map((u) => (
              <div
                key={u.id}
                className="bg-white rounded-xl shadow-lg p-4 flex gap-4"
              >
                <img
                  src={u.thumbnail_url || u.image_url}
                  alt={u.plant_common_name || "Upload"}
                  className="w-24 h-24 object-cover rounded-lg flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700">
                    <span className="font-medium">User selected:</span>{" "}
                    {u.plant_common_name || u.plant_scientific_name}
                  </p>
                  <p className="text-sm text-gray-700">
                    <span className="font-medium">AI prediction:</span>{" "}
                    {u.ai_predicted_name || "N/A"} (
                    {((u.ai_confidence || 0) * 100).toFixed(0)}%)
                  </p>
                  <div className="mt-1">
                    <StatusBadge status={u.ai_status} />
                  </div>

                  <div className="mt-3 flex gap-2 items-center">
                    <button
                      onClick={() => handleApprove(u.id)}
                      className="px-4 py-1.5 bg-green-500 text-white text-sm rounded-lg hover:bg-green-600"
                    >
                      Approve
                    </button>
                    {showRejectInput === u.id ? (
                      <div className="flex gap-2 items-center">
                        <input
                          type="text"
                          placeholder="Reason for rejection"
                          value={rejectReasons[u.id] || ""}
                          onChange={(e) =>
                            setRejectReasons((prev) => ({
                              ...prev,
                              [u.id]: e.target.value,
                            }))
                          }
                          className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:border-red-400"
                        />
                        <button
                          onClick={() => handleReject(u.id)}
                          className="px-4 py-1.5 bg-red-500 text-white text-sm rounded-lg hover:bg-red-600"
                        >
                          Confirm
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setShowRejectInput(u.id)}
                        className="px-4 py-1.5 bg-red-500 text-white text-sm rounded-lg hover:bg-red-600"
                      >
                        Reject
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
