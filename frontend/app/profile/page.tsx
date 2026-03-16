"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useStore } from "@/lib/store";
import { fetchMyUploads, deleteUpload } from "@/lib/api";
import Navbar from "@/components/Navbar";
import StatusBadge from "@/components/StatusBadge";
import type { UserUpload } from "@/lib/types";

export default function ProfilePage() {
  const user = useStore((s) => s.user);
  const router = useRouter();
  const [uploads, setUploads] = useState<UserUpload[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) {
      router.push("/login");
      return;
    }
    fetchMyUploads()
      .then((data) => setUploads(data.uploads || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [user, router]);

  const handleDelete = async (id: string) => {
    try {
      await deleteUpload(id);
      setUploads((prev) => prev.filter((u) => u.id !== id));
    } catch {
      // delete failed
    }
  };

  if (!user) return null;

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <div className="max-w-4xl mx-auto pt-20 px-4">
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">
            {user.display_name}
          </h1>
          <p className="text-gray-600">{user.email}</p>
        </div>

        <div className="bg-white rounded-xl shadow-lg overflow-hidden">
          <h2 className="text-lg font-semibold text-gray-900 p-6 pb-3">
            My Uploads
          </h2>
          {loading ? (
            <div className="p-6 text-gray-500">Loading...</div>
          ) : uploads.length === 0 ? (
            <div className="p-6 text-gray-500">No uploads yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50 text-left text-sm text-gray-600">
                  <tr>
                    <th className="px-6 py-3">Photo</th>
                    <th className="px-6 py-3">Plant</th>
                    <th className="px-6 py-3">Date</th>
                    <th className="px-6 py-3">AI Status</th>
                    <th className="px-6 py-3">Moderation</th>
                    <th className="px-6 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {uploads.map((u) => (
                    <tr key={u.id}>
                      <td className="px-6 py-3">
                        <img
                          src={u.thumbnail_url || u.image_url}
                          alt={u.plant_common_name || "Upload"}
                          className="w-12 h-12 object-cover rounded"
                        />
                      </td>
                      <td className="px-6 py-3 text-sm text-gray-900">
                        {u.plant_common_name || u.plant_scientific_name}
                      </td>
                      <td className="px-6 py-3 text-sm text-gray-600">
                        {new Date(u.submitted_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-3">
                        <StatusBadge status={u.ai_status} />
                      </td>
                      <td className="px-6 py-3">
                        <StatusBadge status={u.moderation_status} />
                      </td>
                      <td className="px-6 py-3">
                        {u.moderation_status === "pending" && (
                          <button
                            onClick={() => handleDelete(u.id)}
                            className="text-sm text-red-600 hover:underline"
                          >
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
