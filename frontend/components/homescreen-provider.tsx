"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type DisplayMode = "browser" | "standalone";

type HomescreenContextValue = {
  displayMode: DisplayMode;
  isApple: boolean;
  isInstallable: boolean;
  promptInstall: () => Promise<boolean>;
};

const HomescreenContext = createContext<HomescreenContextValue>({
  displayMode: "browser",
  isApple: false,
  isInstallable: false,
  promptInstall: async () => false,
});

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

function detectStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const mq = window.matchMedia("(display-mode: standalone)").matches;
  const ios = "standalone" in navigator && Boolean((navigator as Navigator & { standalone?: boolean }).standalone);
  return mq || ios;
}

function detectApple(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  const iOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  return iOS || /Macintosh/.test(ua);
}

export function HomescreenProvider({ children }: { children: ReactNode }) {
  const [displayMode, setDisplayMode] = useState<DisplayMode>("browser");
  const [isApple, setIsApple] = useState(false);
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);

  useEffect(() => {
    const apple = detectApple();
    setIsApple(apple);
    const apply = () => {
      const standalone = detectStandalone();
      setDisplayMode(standalone ? "standalone" : "browser");
      document.documentElement.dataset.displayMode = standalone ? "standalone" : "browser";
      document.documentElement.dataset.apple = apple ? "true" : "false";
    };
    apply();
    const mq = window.matchMedia("(display-mode: standalone)");
    const onChange = () => apply();
    mq.addEventListener?.("change", onChange);

    const onBip = (event: Event) => {
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onBip);

    return () => {
      mq.removeEventListener?.("change", onChange);
      window.removeEventListener("beforeinstallprompt", onBip);
    };
  }, []);

  async function promptInstall(): Promise<boolean> {
    if (!deferred) return false;
    await deferred.prompt();
    const choice = await deferred.userChoice;
    setDeferred(null);
    return choice.outcome === "accepted";
  }

  return (
    <HomescreenContext.Provider
      value={{
        displayMode,
        isApple,
        isInstallable: deferred !== null,
        promptInstall,
      }}
    >
      {children}
    </HomescreenContext.Provider>
  );
}

export function useHomescreen() {
  return useContext(HomescreenContext);
}
