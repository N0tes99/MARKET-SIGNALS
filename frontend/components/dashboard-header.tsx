export function DashboardHeader() {
  return (
    <header className="border-b border-border">
      <div className="container mx-auto flex items-end justify-between px-4 py-8">
        <div>
          <p className="label-caps mb-3">Signal Engine</p>
          <h1 className="text-2xl font-light tracking-tight text-foreground">
            Market intelligence
          </h1>
        </div>
        <div className="flex items-center gap-2 pb-1">
          <span className="idle-dot" />
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
            live
          </span>
        </div>
      </div>
    </header>
  );
}
