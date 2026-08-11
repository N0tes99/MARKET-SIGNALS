"use client";

/** Minimal injected Ethereum provider shape (MetaMask / Rabby / etc.). */
export interface EthereumProvider {
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
}

/** Phantom / Solana injected provider. */
export interface SolanaProvider {
  isPhantom?: boolean;
  publicKey?: { toString: () => string } | null;
  connect: (opts?: { onlyIfTrusted?: boolean }) => Promise<{ publicKey: { toString: () => string } }>;
  signMessage: (
    message: Uint8Array,
    display?: "utf8" | "hex",
  ) => Promise<{ signature: Uint8Array } | Uint8Array>;
}

declare global {
  interface Window {
    ethereum?: EthereumProvider;
    solana?: SolanaProvider;
    phantom?: { solana?: SolanaProvider };
  }
}

export type WalletChain = "ethereum" | "solana" | "sui";

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

export function getEthereumProvider(): EthereumProvider | null {
  if (typeof window === "undefined") return null;
  return window.ethereum ?? null;
}

export function getSolanaProvider(): SolanaProvider | null {
  if (typeof window === "undefined") return null;
  return window.phantom?.solana ?? window.solana ?? null;
}

export async function connectEthereumAddress(): Promise<{
  address: string;
  chainId: number;
}> {
  const eth = getEthereumProvider();
  if (!eth) {
    throw new Error("No Ethereum wallet found. Install MetaMask or another browser wallet.");
  }
  const accounts = (await eth.request({
    method: "eth_requestAccounts",
  })) as string[];
  const address = accounts?.[0];
  if (!address) {
    throw new Error("Wallet returned no account");
  }
  const chainHex = (await eth.request({ method: "eth_chainId" })) as string;
  const chainId = Number.parseInt(chainHex, 16);
  return { address, chainId: Number.isFinite(chainId) ? chainId : 1 };
}

export async function personalSignEthereum(address: string, message: string): Promise<string> {
  const eth = getEthereumProvider();
  if (!eth) {
    throw new Error("No Ethereum wallet found");
  }
  const signature = (await eth.request({
    method: "personal_sign",
    params: [utf8ToHex(message), address],
  })) as string;
  if (!signature) {
    throw new Error("Wallet did not return a signature");
  }
  return signature;
}

export async function connectSolanaAddress(): Promise<{ address: string }> {
  const sol = getSolanaProvider();
  if (!sol) {
    throw new Error("No Solana wallet found. Install Phantom.");
  }
  const connected = await sol.connect();
  const address = connected.publicKey?.toString() ?? sol.publicKey?.toString();
  if (!address) {
    throw new Error("Phantom returned no account");
  }
  return { address };
}

export async function signSolanaMessage(message: string): Promise<string> {
  const sol = getSolanaProvider();
  if (!sol) {
    throw new Error("No Solana wallet found");
  }
  const encoded = new TextEncoder().encode(message);
  const result = await sol.signMessage(encoded, "utf8");
  const signature =
    result instanceof Uint8Array
      ? result
      : result.signature instanceof Uint8Array
        ? result.signature
        : null;
  if (!signature) {
    throw new Error("Phantom did not return a signature");
  }
  return bytesToBase58(signature);
}

type SuiWalletFeature = {
  connect?: () => Promise<{ accounts?: Array<{ address: string }> }>;
  signPersonalMessage?: (input: {
    message: Uint8Array;
    account?: { address: string };
  }) => Promise<{ signature: string; bytes?: string }>;
};

type StandardWallet = {
  name: string;
  accounts?: Array<{ address: string }>;
  features: Record<string, SuiWalletFeature | unknown>;
};

function asWalletFeature(value: unknown): SuiWalletFeature | null {
  if (!value || typeof value !== "object") return null;
  return value as SuiWalletFeature;
}

export async function connectSuiAddress(): Promise<{
  address: string;
  wallet: StandardWallet;
}> {
  const { getWallets } = await import("@mysten/wallet-standard");
  const wallets = getWallets().get() as unknown as StandardWallet[];
  const wallet =
    wallets.find((w) => Boolean(asWalletFeature(w.features["sui:signPersonalMessage"]))) ??
    null;
  if (!wallet) {
    throw new Error("No Sui wallet found. Install Slush or the Sui Wallet extension.");
  }

  const connectFeature =
    asWalletFeature(wallet.features["standard:connect"]) ??
    asWalletFeature(wallet.features["sui:connect"]);
  if (connectFeature?.connect) {
    await connectFeature.connect();
  }

  const address = wallet.accounts?.[0]?.address;
  if (!address) {
    throw new Error("Sui wallet returned no account");
  }
  return { address, wallet };
}

export async function signSuiMessage(wallet: StandardWallet, message: string): Promise<string> {
  const signFeature = asWalletFeature(wallet.features["sui:signPersonalMessage"]);
  if (!signFeature?.signPersonalMessage) {
    throw new Error("Sui wallet cannot sign personal messages");
  }
  const address = wallet.accounts?.[0]?.address;
  if (!address) {
    throw new Error("Sui wallet has no connected account");
  }
  const encoded = new TextEncoder().encode(message);
  const result = await signFeature.signPersonalMessage({
    message: encoded,
    account: { address },
  });
  if (!result?.signature) {
    throw new Error("Sui wallet did not return a signature");
  }
  return result.signature;
}
