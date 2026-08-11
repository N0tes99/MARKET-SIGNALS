"use client";

/** Minimal injected Ethereum provider shape (MetaMask / Rabby / etc.). */
export interface EthereumProvider {
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
}

declare global {
  interface Window {
    ethereum?: EthereumProvider;
  }
}

export function getEthereumProvider(): EthereumProvider | null {
  if (typeof window === "undefined") return null;
  return window.ethereum ?? null;
}

export function utf8ToHex(message: string): string {
  const bytes = new TextEncoder().encode(message);
  let hex = "0x";
  for (const b of bytes) {
    hex += b.toString(16).padStart(2, "0");
  }
  return hex;
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
