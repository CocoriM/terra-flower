"use client";

import { useStore } from "@/lib/store";

export default function UploadButton() {
  const user = useStore((s) => s.user);
  const openUploadModal = useStore((s) => s.openUploadModal);

  if (!user) return null;

  return (
    <button
      onClick={openUploadModal}
      className="w-full mt-4 px-4 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 transition-colors font-medium"
      aria-label="Upload a photo"
    >
      Upload a Photo
    </button>
  );
}
