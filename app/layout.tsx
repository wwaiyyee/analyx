import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { WalletProvider } from "@/lib/wallet/provider";
import { Navbar } from "@/components/navbar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Analyx — Evidence-First AI Data Analyst",
  description:
    "Deterministic analytics engine anchored with Solana on-chain cryptographic attestations. Zero hallucinated metrics, every claim backed by proof.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full dark antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[#090a0f] text-zinc-100 selection:bg-cyan-500/30 selection:text-cyan-200">
        <WalletProvider>
          <Navbar />
          <main className="flex-1 flex flex-col">{children}</main>
        </WalletProvider>
      </body>
    </html>
  );
}
