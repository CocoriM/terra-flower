"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useStore } from "@/lib/store";

export default function Navbar() {
  const user = useStore((s) => s.user);
  const setUser = useStore((s) => s.setUser);
  const setAccessToken = useStore((s) => s.setAccessToken);
  const pathname = usePathname();

  const isGlobe = pathname === "/";
  const bgClass = isGlobe
    ? "bg-transparent"
    : "bg-white border-b border-gray-200";

  const handleLogout = () => {
    setUser(null);
    setAccessToken(null);
  };

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3 ${bgClass}`}
    >
      <Link
        href="/"
        className={`text-xl font-bold ${isGlobe ? "text-white" : "text-gray-900"}`}
      >
        TerraFlora
      </Link>

      <div className="flex items-center gap-4">
        {user ? (
          <>
            <span
              className={`text-sm ${isGlobe ? "text-white" : "text-gray-700"}`}
            >
              {user.display_name}
            </span>
            <Link
              href="/profile"
              className={`text-sm ${isGlobe ? "text-white hover:text-gray-200" : "text-gray-600 hover:text-gray-900"}`}
            >
              Profile
            </Link>
            {(user.role === "moderator" || user.role === "admin") && (
              <Link
                href="/moderation"
                className={`text-sm ${isGlobe ? "text-white hover:text-gray-200" : "text-gray-600 hover:text-gray-900"}`}
              >
                Moderation
              </Link>
            )}
            <button
              onClick={handleLogout}
              className={`text-sm ${isGlobe ? "text-white hover:text-gray-200" : "text-gray-600 hover:text-gray-900"}`}
            >
              Logout
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className={`text-sm ${isGlobe ? "text-white hover:text-gray-200" : "text-gray-600 hover:text-gray-900"}`}
          >
            Login
          </Link>
        )}
      </div>
    </nav>
  );
}
