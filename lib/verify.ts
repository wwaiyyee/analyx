/**
 * Client-Side & Full Public Attestation Verifier
 * Verifies cryptographic integrity of AttestationBundle and on-chain Solana anchors per §11.3.
 */

import { api, PublicVerifyResponse, VerificationCheck, OnChainDetails } from "./api";
import { attestationRoot, sha256Hex } from "./hashing";

export interface LocalVerificationResult {
  passed: boolean;
  computedRoot: string;
  expectedRoot?: string;
  checks: VerificationCheck[];
}

export interface FullVerificationResult {
  status: "VERIFIED" | "MODIFIED" | "NOT_ANCHORED" | "INVALID_BUNDLE";
  computedRoot: string;
  checks: VerificationCheck[];
  onChain?: OnChainDetails | null;
}

/**
 * Execute client-side cryptographic verification without requiring server trust:
 * 1. Validates bundle structure
 * 2. If markdown text provided, verifies SHA-256 matches bundle.report.sha256
 * 3. Computes attestation root via canonical RFC 8785 JCS
 */
export async function verifyLocalBundle(
  bundle: Record<string, unknown>,
  reportMarkdown?: string
): Promise<LocalVerificationResult> {
  const checks: VerificationCheck[] = [];

  // Check 1: Bundle schema
  const hasReport = Boolean(bundle.report && typeof bundle.report === "object");
  const hasDatasets = Array.isArray(bundle.datasets);
  const hasEvidence = Array.isArray(bundle.evidence);
  const hasEngine = Boolean(bundle.engine && typeof bundle.engine === "object");

  if (!hasReport || !hasDatasets || !hasEvidence || !hasEngine) {
    checks.push({
      name: "bundle_schema",
      passed: false,
      detail: "Bundle missing required fields (report, datasets, evidence, or engine)",
    });
    return {
      passed: false,
      computedRoot: "",
      checks,
    };
  }

  checks.push({
    name: "bundle_schema",
    passed: true,
    detail: `Valid schema: ${(bundle.datasets as unknown[]).length} datasets, ${(bundle.evidence as unknown[]).length} evidence items`,
  });

  // Check 2: Report Hash Match (if markdown provided)
  const reportObj = bundle.report as Record<string, unknown>;
  const bundleReportSha = String(reportObj.sha256 || "");

  if (reportMarkdown) {
    const computedSha = await sha256Hex(reportMarkdown);
    const matches = computedSha === bundleReportSha;
    checks.push({
      name: "report_content_integrity",
      passed: matches,
      detail: matches
        ? `Report SHA-256 matches (${computedSha.slice(0, 16)}...)`
        : `Hash mismatch! Computed ${computedSha.slice(0, 8)} != Bundle ${bundleReportSha.slice(0, 8)}`,
    });
  } else {
    checks.push({
      name: "report_content_integrity",
      passed: true,
      detail: `Report reference registered with SHA-256 (${bundleReportSha.slice(0, 16)}...)`,
    });
  }

  // Check 3: Canonical Attestation Root Computation
  let computedRoot = "";
  try {
    computedRoot = await attestationRoot(bundle);
    checks.push({
      name: "canonical_root_calculation",
      passed: true,
      detail: `Root successfully derived via RFC 8785: ${computedRoot}`,
    });
  } catch (err: unknown) {
    checks.push({
      name: "canonical_root_calculation",
      passed: false,
      detail: `Canonical hashing failed: ${err instanceof Error ? err.message : String(err)}`,
    });
    return {
      passed: false,
      computedRoot: "",
      checks,
    };
  }

  const allPassed = checks.every((c) => c.passed);
  return {
    passed: allPassed,
    computedRoot,
    checks,
  };
}

/**
 * Execute complete multi-layer verification (client cryptographic checks + Solana on-chain RPC query).
 */
export async function verifyFullAttestation(options: {
  bundle: Record<string, unknown>;
  reportMarkdown?: string;
  txSignature?: string;
  cluster?: "devnet" | "mainnet-beta";
}): Promise<FullVerificationResult> {
  // Step 1: Local client-side checks
  const localRes = await verifyLocalBundle(options.bundle, options.reportMarkdown);

  if (!localRes.passed) {
    return {
      status: "INVALID_BUNDLE",
      computedRoot: localRes.computedRoot,
      checks: localRes.checks,
      onChain: null,
    };
  }

  // Step 2: Query public verification endpoint for on-chain anchoring
  try {
    const backendRes: PublicVerifyResponse = await api.verify.verifyBundle({
      bundle: options.bundle,
      report_markdown: options.reportMarkdown,
      report_sha256: (options.bundle.report as Record<string, unknown>)?.sha256 as string,
      tx_signature: options.txSignature,
      cluster: options.cluster || "devnet",
    });

    return {
      status: backendRes.status,
      computedRoot: localRes.computedRoot,
      checks: [...localRes.checks, ...backendRes.checks],
      onChain: backendRes.on_chain || null,
    };
  } catch (err: unknown) {
    // If backend verify failed or offline
    return {
      status: "NOT_ANCHORED",
      computedRoot: localRes.computedRoot,
      checks: [
        ...localRes.checks,
        {
          name: "on_chain_query",
          passed: false,
          detail: `Could not verify Solana RPC: ${err instanceof Error ? err.message : String(err)}`,
        },
      ],
      onChain: null,
    };
  }
}
