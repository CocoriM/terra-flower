"use client";

import { useState, useRef, useCallback } from "react";
import { useStore } from "@/lib/store";
import { uploadPhoto, confirmUpload } from "@/lib/api";
import type { AIResult } from "@/lib/types";

type Step = "upload" | "results" | "done";

export default function UploadModal() {
  const isOpen = useStore((s) => s.isUploadModalOpen);
  const closeModal = useStore((s) => s.closeUploadModal);

  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [locationText, setLocationText] = useState("");
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [consent, setConsent] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [results, setResults] = useState<AIResult[]>([]);
  const [confirmResult, setConfirmResult] = useState<{
    ai_status: string;
    moderation_status: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const f = files[0];
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setError(null);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    handleFileChange(e.dataTransfer.files);
  }, []);

  const handleUseMyLocation = () => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLng(pos.coords.longitude);
        setLocationText(
          `${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`
        );
      },
      () => setError("Could not get your location")
    );
  };

  const handleSubmit = async () => {
    if (!file || !consent) return;
    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("image", file);
    if (lat !== null) formData.append("latitude", String(lat));
    if (lng !== null) formData.append("longitude", String(lng));
    if (locationText) formData.append("location_text", locationText);

    try {
      const data = await uploadPhoto(formData);
      setUploadId(data.id);
      setResults(data.ai_top_results || []);
      setStep("results");
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Upload failed. Please try again."
      );
    } finally {
      setUploading(false);
    }
  };

  const handleConfirm = async (plantId: string) => {
    if (!uploadId) return;
    setConfirming(true);
    setError(null);

    try {
      const data = await confirmUpload(uploadId, plantId);
      setConfirmResult(data);
      setStep("done");
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Confirmation failed. Please try again."
      );
    } finally {
      setConfirming(false);
    }
  };

  const handleClose = () => {
    setStep("upload");
    setFile(null);
    setPreview(null);
    setLocationText("");
    setLat(null);
    setLng(null);
    setConsent(false);
    setUploadId(null);
    setResults([]);
    setConfirmResult(null);
    setError(null);
    closeModal();
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-label="Upload photo"
    >
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full mx-4 p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold text-gray-900">
            {step === "upload" && "Upload a Plant Photo"}
            {step === "results" && "AI Identification Results"}
            {step === "done" && "Submitted!"}
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 text-2xl"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        {/* Step 1: Upload image */}
        {step === "upload" && (
          <div className="space-y-4">
            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => fileRef.current?.click()}
              className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-gray-400 transition-colors"
            >
              {preview ? (
                <img
                  src={preview}
                  alt="Preview"
                  className="max-h-48 mx-auto rounded"
                />
              ) : (
                <div className="text-gray-500">
                  <p className="text-lg">Drop an image here</p>
                  <p className="text-sm">or click to browse</p>
                </div>
              )}
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => handleFileChange(e.target.files)}
                className="hidden"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Location
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={locationText}
                  onChange={(e) => setLocationText(e.target.value)}
                  placeholder="e.g. Central Park, New York"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-emerald-500"
                />
                <button
                  type="button"
                  onClick={handleUseMyLocation}
                  className="px-3 py-2 bg-gray-100 border border-gray-300 rounded-lg text-sm hover:bg-gray-200"
                >
                  Use my location
                </button>
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                className="rounded"
              />
              I confirm this is my own photo
            </label>

            {error && (
              <p className="text-sm text-red-600 bg-red-50 rounded-lg p-3">
                {error}
              </p>
            )}

            <button
              onClick={handleSubmit}
              disabled={!file || !consent || uploading}
              className="w-full py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {uploading ? (
                <>
                  <svg
                    className="animate-spin h-4 w-4"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  Identifying...
                </>
              ) : (
                "Identify This Plant"
              )}
            </button>
          </div>
        )}

        {/* Step 2: AI results */}
        {step === "results" && (
          <div className="space-y-4">
            {results.length > 0 ? (
              <>
                <p className="text-sm text-gray-600">
                  This looks like:
                </p>
                <div className="space-y-3">
                  {results.map((r, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 p-3 border border-gray-200 rounded-lg"
                    >
                      {r.matched_plant_image && (
                        <img
                          src={r.matched_plant_image}
                          alt={r.common_name}
                          className="w-12 h-12 rounded-full object-cover flex-shrink-0"
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-gray-900 text-sm">
                          {r.common_name}
                        </p>
                        <p className="text-xs text-gray-500 italic">
                          {r.scientific_name}
                        </p>
                        <div className="mt-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-emerald-500 rounded-full"
                            style={{ width: `${(r.confidence * 100).toFixed(0)}%` }}
                          />
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {(r.confidence * 100).toFixed(0)}% confidence
                        </p>
                      </div>
                      {r.matched_plant_id && (
                        <button
                          onClick={() => handleConfirm(r.matched_plant_id!)}
                          disabled={confirming}
                          className="px-3 py-1.5 bg-emerald-500 text-white text-sm rounded-lg hover:bg-emerald-600 disabled:opacity-50 flex-shrink-0"
                        >
                          {confirming ? "..." : i === 0 ? "Yes!" : "This one"}
                        </button>
                      )}
                      {!r.matched_plant_id && (
                        <span className="text-xs text-gray-400 flex-shrink-0">
                          Not in DB
                        </span>
                      )}
                    </div>
                  ))}
                </div>

                {error && (
                  <p className="text-sm text-red-600 bg-red-50 rounded-lg p-3">
                    {error}
                  </p>
                )}

                <button
                  onClick={handleClose}
                  className="w-full py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 text-sm"
                >
                  None of these match
                </button>
              </>
            ) : (
              <div className="text-center py-6">
                <p className="text-gray-600">
                  Sorry, we couldn't identify this plant. Try again with a
                  different photo.
                </p>
                <button
                  onClick={handleClose}
                  className="mt-4 px-6 py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600"
                >
                  Close
                </button>
              </div>
            )}
          </div>
        )}

        {/* Step 3: Confirmation */}
        {step === "done" && confirmResult && (
          <div className="space-y-4">
            <div
              className={`border rounded-lg p-4 ${
                confirmResult.ai_status === "approved_auto"
                  ? "bg-green-50 border-green-200"
                  : "bg-yellow-50 border-yellow-200"
              }`}
            >
              {confirmResult.ai_status === "approved_auto" ? (
                <p className="font-medium text-green-800">
                  Photo approved! It's now in the community gallery.
                </p>
              ) : (
                <p className="font-medium text-yellow-800">
                  Photo submitted for review. A moderator will check it soon.
                </p>
              )}
            </div>
            <button
              onClick={handleClose}
              className="w-full py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
