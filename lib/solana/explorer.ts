/**
 * Solana Explorer Link Builder
 * Generates verified explorer and solscan links for transactions and accounts.
 */

export type SolanaCluster = "devnet" | "mainnet-beta";
export type ExplorerProvider = "solana" | "solscan";

export function getExplorerTxUrl(
  txSignature: string,
  cluster: SolanaCluster = "devnet",
  provider: ExplorerProvider = "solana"
): string {
  if (provider === "solscan") {
    const clusterParam = cluster === "devnet" ? "?cluster=devnet" : "";
    return `https://solscan.io/tx/${txSignature}${clusterParam}`;
  }

  // Default: Solana Explorer
  const clusterParam = cluster === "devnet" ? "?cluster=devnet" : "";
  return `https://explorer.solana.com/tx/${txSignature}${clusterParam}`;
}

export function getExplorerAddressUrl(
  address: string,
  cluster: SolanaCluster = "devnet",
  provider: ExplorerProvider = "solana"
): string {
  if (provider === "solscan") {
    const clusterParam = cluster === "devnet" ? "?cluster=devnet" : "";
    return `https://solscan.io/account/${address}${clusterParam}`;
  }

  const clusterParam = cluster === "devnet" ? "?cluster=devnet" : "";
  return `https://explorer.solana.com/address/${address}${clusterParam}`;
}
