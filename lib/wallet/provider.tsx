"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { api, clearStoredToken, getStoredToken, getStoredWorkspaceId } from "../api";
import { signInWithWallet } from "./sign-in";

interface PhantomProvider {
  isPhantom?: boolean;
  publicKey?: { toBase58(): string; toBuffer(): Uint8Array };
  connect(opts?: { onlyIfTrusted?: boolean }): Promise<{ publicKey: { toBase58(): string } }>;
  disconnect(): Promise<void>;
  signMessage(message: Uint8Array, encoding?: string): Promise<{ signature: Uint8Array }>;
  signAndSendTransaction?(
    transaction: unknown,
    options?: unknown
  ): Promise<{ signature: string }>;
}

declare global {
  interface Window {
    solana?: PhantomProvider;
    phantom?: { solana?: PhantomProvider };
  }
}

export interface WalletContextType {
  publicKey: string | null;
  connected: boolean;
  connecting: boolean;
  token: string | null;
  workspaceId: string | null;
  cluster: "devnet" | "mainnet-beta";
  setCluster: (cluster: "devnet" | "mainnet-beta") => void;
  connect: () => Promise<void>;
  connectDemo: () => Promise<void>;
  disconnect: () => void;
  signMessage: ((message: Uint8Array) => Promise<Uint8Array>) | null;
}

const WalletContext = createContext<WalletContextType | undefined>(undefined);

// Deterministic mock keypair for demo mode when no extension is installed
const DEMO_WALLET_PUBLIC_KEY = "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU";

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [publicKey, setPublicKey] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [workspaceId, setWorkspaceId] = useState<string | null>(() => getStoredWorkspaceId());
  const [connecting, setConnecting] = useState<boolean>(false);
  const [cluster, setCluster] = useState<"devnet" | "mainnet-beta">("devnet");

  const getProvider = useCallback((): PhantomProvider | null => {
    if (typeof window === "undefined") return null;
    if (window.phantom?.solana?.isPhantom) return window.phantom.solana;
    if (window.solana) return window.solana;
    return null;
  }, []);

  const connectDemo = useCallback(async () => {
    setConnecting(true);
    try {
      setPublicKey(DEMO_WALLET_PUBLIC_KEY);
      try {
        const authRes = await api.auth.demo();
        setToken(authRes.token);
        setWorkspaceId(authRes.workspace_id);
      } catch (err) {
        console.warn("Backend demo login failed, fallback to local:", err);
        setToken("demo_token_workspace");
        setWorkspaceId("ws_demo_analyx");
      }
    } finally {
      setConnecting(false);
    }
  }, []);

  const connect = useCallback(async () => {
    setConnecting(true);
    try {
      const provider = getProvider();
      if (!provider) {
        // Fall back to demo mode if no wallet extension is installed
        console.warn("No Solana wallet extension detected. Defaulting to Demo Mode.");
        await connectDemo();
        return;
      }

      const res = await provider.connect();
      const pubkey = res.publicKey.toBase58();
      setPublicKey(pubkey);

      // Perform challenge-response ed25519 authentication
      const signFn = async (msg: Uint8Array): Promise<Uint8Array> => {
        const signResult = await provider.signMessage(msg);
        return signResult.signature;
      };

      const authRes = await signInWithWallet(pubkey, signFn);
      setToken(authRes.token);
      setWorkspaceId(authRes.workspaceId);
    } catch (err) {
      console.error("Wallet connection error:", err);
      throw err;
    } finally {
      setConnecting(false);
    }
  }, [getProvider, connectDemo]);

  const disconnect = useCallback(() => {
    clearStoredToken();
    setToken(null);
    setWorkspaceId(null);
    setPublicKey(null);
    const provider = getProvider();
    if (provider?.disconnect) {
      provider.disconnect().catch(() => {});
    }
  }, [getProvider]);

  const signMessage = useCallback(
    async (message: Uint8Array): Promise<Uint8Array> => {
      const provider = getProvider();
      if (provider && provider.signMessage) {
        const res = await provider.signMessage(message);
        return res.signature;
      }
      return new Uint8Array(64);
    },
    [getProvider]
  );

  return (
    <WalletContext.Provider
      value={{
        publicKey,
        connected: Boolean(token),
        connecting,
        token,
        workspaceId,
        cluster,
        setCluster,
        connect,
        connectDemo,
        disconnect,
        signMessage,
      }}
    >
      {children}
    </WalletContext.Provider>
  );
}

export function useWallet(): WalletContextType {
  const context = useContext(WalletContext);
  if (!context) {
    throw new Error("useWallet must be used within a WalletProvider");
  }
  return context;
}
