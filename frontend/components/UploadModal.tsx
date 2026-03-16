"use client";

import { useState, useRef, useCallback } from "react";
import { useStore } from "@/lib/store";
import { uploadPhoto } from "@/lib/api";

export default function UploadModal() {
  const isOpen = useStore((s) => s.isUploadModalOpen);
  const closeModal = useStore((s) => s.closeUploadModal);
  const selectedPlant = useStore((s) => s.selectedPlant);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [locationText, setLocationText] = useState("");
  const [lat, setLat] = useState<number | null>(null);
  const [lng, setLng] = useState<number | null>(null);
  const [consent, setConsent] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const f = files[0];
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
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
    if (!file || !selectedPlant || !consent) return;
    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("image", file);
    formData.append("trefle_plant_id", String(selectedPlant.trefle_id));
    formData.append("plant_scientific_name", selectedPlant.scientific_name);
    if (selectedPlant.common_name)
      formData.append("plant_common_name", selectedPlant.common_name);
    formData.append("plant_type", selectedPlant.plant_type);
    if (lat !== null) formData.append("latitude", String(lat));
    if (lng !== null) formData.append("longitude", String(lng));
    if (locationText) formData.append("location_text", locationText);

    try {
      const data = await uploadPhoto(formData);
      setResult(data);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || "Upload failed. Please try again."
      );
    } finally {
      setUploading(false);
    }
  };

  const handleClose = () => {
    setFile(null);
    setPreview(null);
    setLocationText("");
    setLat(null);
    setLng(null);
    setConsent(false);
    setResult(null);
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
          <h2 className="text-xl font-bold text-gray-900">Upload a Photo</h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 text-2xl"
            aria-label="Close"
          >
            &times;
          </button>
        </div>

        {result ? (
          <div className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="font-medium text-green-800">Upload successful!</p>
              {result.ai_predicted_name && (
                <p className="text-sm text-green-700 mt-1">
                  AI suggests: {result.ai_predicted_name} (
                  {((result.ai_confidence || 0) * 100).toFixed(0)}% confidence)
                </p>
              )}
              <p className="text-sm text-green-700 mt-1">
                Status: {result.ai_status?.replace(/_/g, " ")}
              </p>
            </div>
            <button
              onClick={handleClose}
              className="w-full py-2 bg-emerald-500 text-white rounded-lg hover:bg-emerald-600"
            >
              Done
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Dropzone */}
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

            {/* Plant name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Plant
              </label>
              <input
                type="text"
                value={
                  selectedPlant?.common_name ||
                  selectedPlant?.scientific_name ||
                  ""
                }
                readOnly
                className="w-full px-3 py-2 bg-gray-100 border border-gray-200 rounded-lg text-gray-600"
              />
            </div>

            {/* Location */}
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

            {/* Consent */}
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
                  Uploading...
                </>
              ) : (
                "Submit"
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
