"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  fetchHealth,
  fetchMe,
  loginAccount,
  logoutAccount,
  registerAccount,
  resendVerification,
  verifyEmailToken,
  walletChallenge,
  walletVerify,
  type AuthUser,
} from "@/services/api";
import {
  connectEthereumAddress,
  connectSolanaAddress,
  connectSuiAddress,
  personalSignEthereum,
  signSolanaMessage,
  signSuiMessage,
  type WalletChain,
} from "@/lib/ethereum-wallet";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<AuthUser>;
  loginWithWallet: (chain: WalletChain) => Promise<AuthUser>;
  register: (email: string, username: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  verifyEmail: (token: string) => Promise<AuthUser>;
  resendVerificationEmail: (email?: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const me = await fetchMe();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Public /health wakes a sleeping Render dyno while /auth/me is in flight.
    void fetchHealth(12_000).catch(() => undefined);
    void refresh();
    const id = window.setInterval(() => {
      void fetchHealth(8_000).catch(() => undefined);
    }, 4 * 60_000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const next = await loginAccount(email, password);
    setUser(next);
    return next;
  }, []);

  const loginWithWallet = useCallback(async (chain: WalletChain) => {
    if (chain === "ethereum") {
      const { address, chainId } = await connectEthereumAddress();
      const challenge = await walletChallenge({
        chain: "ethereum",
        address,
        chain_id: chainId,
      });
      const signature = await personalSignEthereum(challenge.address, challenge.message);
      const next = await walletVerify({
        chain: "ethereum",
        address: challenge.address,
        signature,
        nonce: challenge.nonce,
      });
      setUser(next);
      return next;
    }

    if (chain === "solana") {
      const { address } = await connectSolanaAddress();
      const challenge = await walletChallenge({
        chain: "solana",
        address,
      });
      const signature = await signSolanaMessage(challenge.message);
      const next = await walletVerify({
        chain: "solana",
        address: challenge.address,
        signature,
        nonce: challenge.nonce,
      });
      setUser(next);
      return next;
    }

    const { address } = await connectSuiAddress();
    const challenge = await walletChallenge({
      chain: "sui",
      address,
    });
    const signature = await signSuiMessage(challenge.address, challenge.message);
    const next = await walletVerify({
      chain: "sui",
      address: challenge.address,
      signature,
      nonce: challenge.nonce,
    });
    setUser(next);
    return next;
  }, []);

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      const next = await registerAccount(email, username, password);
      if (next.email_verified) {
        setUser(next);
      }
      return next;
    },
    [],
  );

  const logout = useCallback(async () => {
    await logoutAccount();
    setUser(null);
  }, []);

  const verifyEmail = useCallback(async (token: string) => {
    const next = await verifyEmailToken(token);
    setUser(next);
    return next;
  }, []);

  const resendVerificationEmail = useCallback(async (email?: string) => {
    await resendVerification(email);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      refresh,
      login,
      loginWithWallet,
      register,
      logout,
      verifyEmail,
      resendVerificationEmail,
    }),
    [
      user,
      loading,
      refresh,
      login,
      loginWithWallet,
      register,
      logout,
      verifyEmail,
      resendVerificationEmail,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
