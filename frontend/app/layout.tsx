import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TerraFlora",
  description:
    "An interactive 3D globe platform for exploring plant species around the world.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="w-full h-full">{children}</body>
    </html>
  );
}
