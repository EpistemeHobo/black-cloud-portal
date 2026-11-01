import type { Metadata } from "next";
import { PrimeReactProvider } from "primereact/api";
import AppShell from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gargantua Internal Developer Portal",
  description: "ทุกระบบของ Gargantua ใครเป็นเจ้าของ และอยู่ในขั้นตอนใดของการพัฒนา",
  // The sign-in card's black hole. public/favicon.svg is the source; the PNGs
  // and favicon.ico are exported from it for browsers that can't use SVG.
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16x16.png", sizes: "16x16", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  manifest: "/site.webmanifest",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body>
        <PrimeReactProvider>
          <AppShell>{children}</AppShell>
        </PrimeReactProvider>
      </body>
    </html>
  );
}
