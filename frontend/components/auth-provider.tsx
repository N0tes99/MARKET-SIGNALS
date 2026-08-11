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
  personalSignEthereum,
} from "@/lib/ethereum-wallet";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<AuthUser>;
  loginWithEthereum: () => Promise<AuthUser>;
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
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const next = await loginAccount(email, password);
    setUser(next);
    return next;
  }, []);

  const loginWithEthereum = useCallback(async () => {
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
  }, []);

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      const next = await registerAccount(email, username, password);
      // Session only when auto-verified (local/dev without SMTP)
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
      loginWithEthereum,
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
      loginWithEthereum,
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
