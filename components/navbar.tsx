"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useWallet } from "@/lib/wallet/provider";
import { Shield, Wallet, CheckCircle2, ChevronDown, ExternalLink, Sparkles, LogOut } from "lucide-react";

export function Navbar() {
  const {
    connected,
    connecting,
    publicKey,
    cluster,
    setCluster,
    connect,
    connectDemo,
    disconnect,
  } = useWallet();

  const [networkDropdown, setNetworkDropdown] = useState(false);

  const truncatedKey = publicKey
    ? `${publicKey.slice(0, 4)}...${publicKey.slice(-4)}`
    : null;

  return (
    <header className="sticky top-0 z-50 w-full border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-tr from-cyan-500 to-indigo-600 shadow-md shadow-cyan-500/20 group-hover:shadow-cyan-500/40 transition">
              <Shield className="h-5 w-5 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold tracking-tight text-white text-lg leading-tight">
                Analyx
              </span>
              <span className="text-[10px] font-mono tracking-wider uppercase text-zinc-400">
                Evidence-First AI
              </span>
            </div>
          </Link>

          {/* Nav links */}
          <nav className="hidden md:flex items-center gap-5 text-sm font-medium">
            <Link
              href="/workspace"
              className="text-zinc-300 hover:text-white transition flex items-center gap-1.5"
            >
              Workspace
            </Link>
            <Link
              href="/verify"
              className="text-zinc-300 hover:text-white transition flex items-center gap-1.5"
            >
              Public Verifier
            </Link>
            <a
              href="https://solana.com"
              target="_blank"
              rel="noreferrer"
              className="text-zinc-500 hover:text-zinc-300 transition flex items-center gap-1 text-xs"
            >
              Solana Anchor
              <ExternalLink className="h-3 w-3" />
            </a>
          </nav>
        </div>

        {/* Right Actions: Network badge + Wallet chip */}
        <div className="flex items-center gap-3">
          {/* Cluster Selector */}
          <div className="relative">
            <button
              onClick={() => setNetworkDropdown(!networkDropdown)}
              className="flex items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900/90 px-3 py-1.5 text-xs font-mono text-zinc-300 hover:border-zinc-700 transition"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>{cluster === "devnet" ? "Solana Devnet" : "Mainnet-Beta"}</span>
              <ChevronDown className="h-3 w-3 text-zinc-400" />
            </button>

            {networkDropdown && (
              <div className="absolute right-0 mt-2 w-40 rounded-lg border border-zinc-800 bg-zinc-900 py-1 shadow-xl z-50">
                <button
                  onClick={() => {
                    setCluster("devnet");
                    setNetworkDropdown(false);
                  }}
                  className={`flex w-full items-center px-3 py-2 text-xs font-mono text-left transition ${
                    cluster === "devnet"
                      ? "text-cyan-400 bg-zinc-800/60 font-semibold"
                      : "text-zinc-300 hover:bg-zinc-800/40"
                  }`}
                >
                  Solana Devnet
                </button>
                <button
                  onClick={() => {
                    setCluster("mainnet-beta");
                    setNetworkDropdown(false);
                  }}
                  className={`flex w-full items-center px-3 py-2 text-xs font-mono text-left transition ${
                    cluster === "mainnet-beta"
                      ? "text-cyan-400 bg-zinc-800/60 font-semibold"
                      : "text-zinc-300 hover:bg-zinc-800/40"
                  }`}
                >
                  Mainnet-Beta
                </button>
              </div>
            )}
          </div>

          {/* Wallet Chip */}
          {connected && publicKey ? (
            <div className="flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900/90 pl-3 pr-1.5 py-1 text-xs font-mono text-zinc-200">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              <span className="font-semibold text-zinc-100">{truncatedKey}</span>
              <button
                onClick={disconnect}
                title="Disconnect wallet"
                className="ml-1 rounded-full p-1 text-zinc-400 hover:bg-zinc-800 hover:text-rose-400 transition"
              >
                <LogOut className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={connectDemo}
                disabled={connecting}
                className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-zinc-700/80 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:bg-zinc-800 hover:text-white transition"
              >
                <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
                Demo Mode
              </button>
              <button
                onClick={connect}
                disabled={connecting}
                className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-cyan-500 to-indigo-600 px-4 py-1.5 text-xs font-semibold text-white shadow-md shadow-cyan-500/20 hover:opacity-95 hover:shadow-cyan-500/30 transition disabled:opacity-50"
              >
                <Wallet className="h-3.5 w-3.5" />
                {connecting ? "Connecting..." : "Connect Wallet"}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
