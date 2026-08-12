/** Dusk water backdrop — finer mist, horizon, a slow breeze. */
export function VoidBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-background">
      <div className="void-depth absolute inset-0" />
      <div className="void-sea absolute inset-0" />
      <div className="void-breeze absolute inset-0" />
      <div className="void-vignette absolute inset-0" />
      <div className="void-grain absolute inset-0" />
      <div className="void-horizon absolute inset-x-[10%] top-[68%] h-px opacity-80" />
      <div className="void-horizon-glow absolute inset-x-[2%] top-[68%] h-28 -translate-y-1/2" />
    </div>
  );
}
