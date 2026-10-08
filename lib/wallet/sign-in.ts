/**
 * Solana Wallet Nonce Challenge Sign-In Flow
 * Implements ed25519 challenge-response authentication per §6.1.
 */

import { api, setStoredToken } from "../api";

export interface SignInResult {
  token: string;
  workspaceId: string;
  wallet: string;
}

/**
 * Convert Uint8Array to Base64 string for signature transport.
 */
function uint8ArrayToBase64(bytes: Uint8Array): string {
  let binary = "";
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Execute the 2-step challenge-response authentication flow:
 * 1. Fetch challenge nonce & message from backend: POST /api/auth/nonce
 * 2. Prompt wallet to sign message bytes
 * 3. Verify signature on backend: POST /api/auth/verify
 * 4. Store returned JWT in localStorage
 */
export async function signInWithWallet(
  walletPublicKey: string,
  signMessage: (message: Uint8Array) => Promise<Uint8Array>
): Promise<SignInResult> {
  // Step 1: Request single-use nonce challenge
  const { message } = await api.auth.getNonce(walletPublicKey);

  // Step 2: Sign message using user's wallet
  const messageBytes = new TextEncoder().encode(message);
  const signatureBytes = await signMessage(messageBytes);
  const signatureBase64 = uint8ArrayToBase64(signatureBytes);

  // Step 3: Verify signature on backend
  const { token, workspace_id } = await api.auth.verify(
    walletPublicKey,
    signatureBase64,
    message
  );

  // Step 4: Persist JWT token
  setStoredToken(token, workspace_id);

  return {
    token,
    workspaceId: workspace_id,
    wallet: walletPublicKey,
  };
}
