import { DashboardHeader } from "@/components/dashboard-header";
import { AssetGrid } from "@/components/asset-grid";

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <DashboardHeader />
      <div className="container mx-auto px-4 pb-16 pt-2">
        <AssetGrid />
      </div>
    </main>
  );
}
