/**
 * Canonical Hashing and RFC 8785 JSON Canonicalization Scheme (JCS).
 * TypeScript mirror of backend/core/hashing.py.
 * Must produce byte-for-byte identical results for identical inputs.
 */

export class FloatNotAllowedError extends Error {
  constructor(val: number) {
    super(`Floats are not permitted in canonical hashing (${val}). Use integers or decimal strings.`);
    this.name = "FloatNotAllowedError";
  }
}

/**
 * Escapes string according to RFC 8785 §3.2.2.2.
 */
export function escapeJcsString(str: string): string {
  let out = '"';
  for (let i = 0; i < str.length; i++) {
    const code = str.charCodeAt(i);
    const char = str[i];
    if (char === '"') {
      out += '\\"';
    } else if (char === "\\") {
      out += "\\\\";
    } else if (char === "\b") {
      out += "\\b";
    } else if (char === "\f") {
      out += "\\f";
    } else if (char === "\n") {
      out += "\\n";
    } else if (char === "\r") {
      out += "\\r";
    } else if (char === "\t") {
      out += "\\t";
    } else if (code < 0x20) {
      out += "\\u" + code.toString(16).padStart(4, "0");
    } else {
      out += char;
    }
  }
  out += '"';
  return out;
}

/**
 * Compare two strings according to UTF-16 code units (RFC 8785 §3.2.3).
 */
export function compareUtf16(a: string, b: string): number {
  const minLen = Math.min(a.length, b.length);
  for (let i = 0; i < minLen; i++) {
    const diff = a.charCodeAt(i) - b.charCodeAt(i);
    if (diff !== 0) return diff;
  }
  return a.length - b.length;
}

/**
 * Serialize any object to RFC 8785 canonical JSON string.
 * Strictly throws FloatNotAllowedError on non-integer numbers.
 */
export function jcs(obj: unknown): string {
  if (obj === null || obj === undefined) return "null";
  if (typeof obj === "boolean") return obj ? "true" : "false";
  if (typeof obj === "number") {
    if (!Number.isInteger(obj)) {
      throw new FloatNotAllowedError(obj);
    }
    return obj.toString();
  }
  if (typeof obj === "string") return escapeJcsString(obj);
  if (Array.isArray(obj)) {
    return "[" + obj.map(jcs).join(",") + "]";
  }
  if (typeof obj === "object") {
    const keys = Object.keys(obj as Record<string, unknown>).sort(compareUtf16);
    const entries = keys.map(
      (k) => escapeJcsString(k) + ":" + jcs((obj as Record<string, unknown>)[k])
    );
    return "{" + entries.join(",") + "}";
  }
  throw new TypeError(`Unsupported type in canonical serialization: ${typeof obj}`);
}

/**
 * Encodes object to canonical JSON UTF-8 bytes.
 */
export function jcsBytes(obj: unknown): Uint8Array {
  const jsonStr = jcs(obj);
  return new TextEncoder().encode(jsonStr);
}

/**
 * Computes lowercase hex SHA-256 using standard Web Crypto API.
 */
export async function sha256Hex(data: string | Uint8Array): Promise<string> {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
  const hashBuf = await crypto.subtle.digest("SHA-256", bytes as unknown as BufferSource);
  const hashArr = Array.from(new Uint8Array(hashBuf));
  return hashArr.map((b) => b.toString(16).padStart(2, "0")).join("");
}

/**
 * Computes lowercase hex SHA-256 of canonical JSON representation of object.
 */
export async function hashObj(obj: unknown): Promise<string> {
  const bytes = jcsBytes(obj);
  return sha256Hex(bytes);
}

/**
 * Computes attestation root per §11.2:
 * sha256_hex(b"analyx:v1:attestation\n" + jcs(bundle))
 */
export async function attestationRoot(bundle: Record<string, unknown>): Promise<string> {
  const prefix = new TextEncoder().encode("analyx:v1:attestation\n");
  const bundleBytes = jcsBytes(bundle);
  const combined = new Uint8Array(prefix.length + bundleBytes.length);
  combined.set(prefix, 0);
  combined.set(bundleBytes, prefix.length);
  return sha256Hex(combined);
}

/**
 * Computes canonical table hash per §8.1.
 */
export async function canonicalTableHash(
  rows: Record<string, unknown>[],
  columns?: string[]
): Promise<string> {
  const colNames = columns && columns.length > 0 ? columns : Object.keys(rows[0] || {}).sort();

  const formattedRows: string[][] = rows.map((row) =>
    colNames.map((col) => {
      const val = row[col];
      if (val === null || val === undefined) return "<NULL>";
      if (typeof val === "boolean") return val ? "true" : "false";
      return String(val).trim();
    })
  );

  formattedRows.sort((a, b) => {
    for (let i = 0; i < colNames.length; i++) {
      const cmp = compareUtf16(a[i], b[i]);
      if (cmp !== 0) return cmp;
    }
    return 0;
  });

  const lines = [colNames.join("\t")];
  for (const r of formattedRows) {
    lines.push(r.join("\t"));
  }

  return sha256Hex(lines.join("\n"));
}
