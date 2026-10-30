import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { AppFooter } from "@/components/ui/AppFooter";
import { AppHeader } from "@/components/ui/AppHeader";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Credit Decisioning",
  description:
    "A calibrated credit model, code-derived adverse-action reasons, and a notice verifier proven by mutation testing. A human decides.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body suppressHydrationWarning className="flex min-h-full flex-col font-sans">
        <AppHeader />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">{children}</main>
        <AppFooter />
      </body>
    </html>
  );
}
