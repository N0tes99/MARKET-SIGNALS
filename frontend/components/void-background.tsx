/** Minimal void backdrop — depth, horizon, idle stillness. */
export function VoidBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-background">
      <div className="void-depth absolute inset-0" />
      <div className="void-vignette absolute inset-0" />
      <div className="void-grain absolute inset-0" />
      <div className="void-horizon absolute inset-x-[8%] top-[62%] h-px opacity-80" />
      <div className="void-horizon-glow absolute inset-x-[4%] top-[62%] h-20 -translate-y-1/2" />
    </div>
  );
}
