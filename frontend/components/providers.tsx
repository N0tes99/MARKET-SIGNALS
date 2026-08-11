"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { AuthProvider } from "@/components/auth-provider";
import { ProductAccessGuard } from "@/components/product-access-guard";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            refetchOnWindowFocus: false,
            // No global polling — opt in per-query (e.g. quotes).
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ProductAccessGuard>{children}</ProductAccessGuard>
      </AuthProvider>
    </QueryClientProvider>
  );
}
