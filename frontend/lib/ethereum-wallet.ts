"use client";

/**
 * Phantom-only wallet connectors for Ethereum, Solana, and Sui.
 * Docs: https://docs.phantom.com/
 */

export interface EthereumProvider {
  isPhantom?: boolean;
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
}

export interface SolanaProvider {
  isPhantom?: boolean;
  publicKey?: { toString: () => string } | null;
  connect: (opts?: { onlyIfTrusted?: boolean }) => Promise<{ publicKey: { toString: () => string } }>;
  signMessage: (
    message: Uint8Array,
    display?: "utf8" | "hex",
  ) => Promise<{ signature: Uint8Array } | Uint8Array>;
}

export interface SuiProvider {
  isPhantom?: boolean;
  requestAccount: () => Promise<{ address?: string; publicKey?: { toString: () => string } }>;
  signMessage: (message: Uint8Array, address: string) => Promise<string | { signature: string }>;
}

declare global {
  interface Window {
    phantom?: {
      ethereum?: EthereumProvider;
      solana?: SolanaProvider;
      sui?: SuiProvider;
    };
  }
}

export type WalletChain = "ethereum" | "solana" | "sui";

const PHANTOM_INSTALL_URL = "https://phantom.com/";

function requirePhantom(): NonNullable<Window["phantom"]> {
  if (typeof window === "undefined" || !window.phantom) {
    if (typeof window !== "undefined") {
      window.open(PHANTOM_INSTALL_URL, "_blank", "noopener,noreferrer");
    }
    throw new Error("Phantom wallet not found. Install Phantom, then try again.");
  }
  return window.phantom;
}

export function utf8ToHex(message: string): string {
  const bytes = new TextEncoder().encode(message);
  let hex = "0x";
  for (const b of bytes) {
    hex += b.toString(16).padStart(2, "0");
  }
  return hex;
}

function bytesToBase58(bytes: Uint8Array): string {
  const ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  let zeros = 0;
  while (zeros < bytes.length && bytes[zeros] === 0) zeros += 1;
  const digits = [0];
  for (let i = zeros; i < bytes.length; i += 1) {
    let carry = bytes[i];
    for (let j = 0; j < digits.length; j += 1) {
      carry += digits[j] << 8;
      digits[j] = carry % 58;
      carry = (carry / 58) | 0;
    }
    while (carry > 0) {
      digits.push(carry % 58);
      carry = (carry / 58) | 0;
    }
  }
  let out = "1".repeat(zeros);
  for (let i = digits.length - 1; i >= 0; i -= 1) {
    out += ALPHABET[digits[i]];
  }
  return out;
}

export function getPhantomEthereum(): EthereumProvider {
  const eth = requirePhantom().ethereum;
  if (!eth?.isPhantom) {
    window.open(PHANTOM_INSTALL_URL, "_blank", "noopener,noreferrer");
    throw new Error("Phantom Ethereum provider not available. Update or reinstall Phantom.");
  }
  return eth;
}

export function getPhantomSolana(): SolanaProvider {
  const sol = requirePhantom().solana;
  if (!sol?.isPhantom) {
    window.open(PHANTOM_INSTALL_URL, "_blank", "noopener,noreferrer");
    throw new Error("Phantom Solana provider not available. Update or reinstall Phantom.");
  }
  return sol;
}

export function getPhantomSui(): SuiProvider {
  const sui = requirePhantom().sui;
  if (!sui?.isPhantom) {
    window.open(PHANTOM_INSTALL_URL, "_blank", "noopener,noreferrer");
    throw new Error("Phantom Sui provider not available. Update Phantom to a version that supports Sui.");
  }
  return sui;
}

export async function connectEthereumAddress(): Promise<{
  address: string;
  chainId: number;
}> {
  const eth = getPhantomEthereum();
  const accounts = (await eth.request({
    method: "eth_requestAccounts",
  })) as string[];
  const address = accounts?.[0];
  if (!address) {
    throw new Error("Phantom returned no Ethereum account");
  }
  const chainHex = (await eth.request({ method: "eth_chainId" })) as string;
  const chainId = Number.parseInt(chainHex, 16);
  return { address, chainId: Number.isFinite(chainId) ? chainId : 1 };
}

export async function personalSignEthereum(address: string, message: string): Promise<string> {
  const eth = getPhantomEthereum();
  const signature = (await eth.request({
    method: "personal_sign",
    params: [utf8ToHex(message), address],
  })) as string;
  if (!signature) {
    throw new Error("Phantom did not return an Ethereum signature");
  }
  return signature;
}

export async function connectSolanaAddress(): Promise<{ address: string }> {
  const sol = getPhantomSolana();
  const connected = await sol.connect();
  const address = connected.publicKey?.toString() ?? sol.publicKey?.toString();
  if (!address) {
    throw new Error("Phantom returned no Solana account");
  }
  return { address };
}

export async function signSolanaMessage(message: string): Promise<string> {
  const sol = getPhantomSolana();
  const encoded = new TextEncoder().encode(message);
  const result = await sol.signMessage(encoded, "utf8");
  const signature =
    result instanceof Uint8Array
      ? result
      : result.signature instanceof Uint8Array
        ? result.signature
        : null;
  if (!signature) {
    throw new Error("Phantom did not return a Solana signature");
  }
  return bytesToBase58(signature);
}

export async function connectSuiAddress(): Promise<{ address: string }> {
  const sui = getPhantomSui();
  const account = await sui.requestAccount();
  const address =
    account.address ??
    (typeof account.publicKey?.toString === "function" ? account.publicKey.toString() : undefined);
  if (!address) {
    throw new Error("Phantom returned no Sui account");
  }
  return { address };
}

export async function signSuiMessage(address: string, message: string): Promise<string> {
  const sui = getPhantomSui();
  const encoded = new TextEncoder().encode(message);
  const result = await sui.signMessage(encoded, address);
  const signature = typeof result === "string" ? result : result?.signature;
  if (!signature) {
    throw new Error("Phantom did not return a Sui signature");
  }
  return signature;
}
