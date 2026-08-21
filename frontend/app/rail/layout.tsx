import type { ReactNode } from "react";

import { RailHeader } from "@/components/rail-header";

export default function RailLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#04070a]">
      <RailHeader />
      {children}
    </div>
  );
}
