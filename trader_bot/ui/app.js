(() => {
  const CORE_AGENTS = ["imbalance", "funding", "liquidity", "spread_micro"];
  const SEEN_CAP = 400;
  let after = 0;
  const seen = new Set();
  let inFlight = false;
  let timer = null;

  const grid = document.getElementById("agent-grid");
  const decisionText = document.getElementById("decision-text");
  const decisionMeta = document.getElementById("decision-meta");
  const feed = document.getElementById("event-feed");
  const pillAlive = document.getElementById("pill-alive");
  const pillMode = document.getElementById("pill-mode");
  const pillTick = document.getElementById("pill-tick");

  function tile(name) {
    const el = document.createElement("article");
    el.className = "agent abstain";
    el.dataset.agent = name;
    el.setAttribute("aria-label", `${name} vote`);
    const h = document.createElement("h3");
    h.className = "agent-name";
    h.textContent = name.toUpperCase();
    const vote = document.createElement("p");
    vote.className = "agent-vote";
    vote.textContent = "--";
    const reason = document.createElement("p");
    reason.className = "agent-reason";
    reason.textContent = "waiting";
    el.append(h, vote, reason);
    return el;
  }

  function ensureTiles(names) {
    const want = [...CORE_AGENTS];
    names.forEach((n) => {
      if (n && !want.includes(n)) want.push(n);
    });
    want.forEach((name) => {
      if (!grid.querySelector(`[data-agent="${name}"]`)) {
        grid.appendChild(tile(name));
      }
    });
    // Drop extras that are no longer in the ballot (keep core always).
    [...grid.querySelectorAll(".agent")].forEach((el) => {
      const name = el.dataset.agent;
      if (!want.includes(name) && !CORE_AGENTS.includes(name)) {
        el.remove();
      }
    });
    return want;
  }

  CORE_AGENTS.forEach((name) => grid.appendChild(tile(name)));

  function voteClass(kind, side) {
    if (kind === "enter" && side === "buy") return "enter-buy";
    if (kind === "enter" && side === "sell") return "enter-sell";
    if (kind === "sit_out" || kind === "veto") return kind;
    return "abstain";
  }

  function voteLabel(p) {
    if (!p) return "--";
    if (p.kind === "enter") return `ENTER ${String(p.side || "").toUpperCase()}`;
    return String(p.kind || "--").toUpperCase();
  }

  function renderAgents(proposals) {
    const list = proposals || [];
    const byName = Object.fromEntries(list.map((p) => [p.agent, p]));
    const names = ensureTiles(list.map((p) => p.agent));
    names.forEach((name) => {
      const el = grid.querySelector(`[data-agent="${name}"]`);
      if (!el) return;
      const p = byName[name];
      el.className = `agent ${voteClass(p?.kind, p?.side)}`;
      el.classList.add("flash");
      el.querySelector(".agent-vote").textContent = voteLabel(p);
      const conf =
        p?.confidence != null && Number(p.confidence) > 0
          ? ` · conf ${Math.round(Number(p.confidence))}`
          : "";
      el.querySelector(".agent-reason").textContent = `${p?.reason || "silent"}${conf}`;
      window.setTimeout(() => el.classList.remove("flash"), 120);
    });
  }

  function renderDecision(ens) {
    if (!ens) {
      decisionText.textContent = "WAITING...";
      decisionText.className = "decision";
      decisionMeta.textContent = "No ensemble event yet. Run loop with --ensemble.";
      return;
    }
    const action = ens.action || "sit_out";
    if (action === "enter") {
      decisionText.textContent = `ENTER ${String(ens.side || "").toUpperCase()}`;
      decisionText.className = "decision enter";
    } else {
      decisionText.textContent = "SIT OUT";
      decisionText.className = "decision sit";
    }
    const agree = (ens.agreeing || []).join("+") || "none";
    decisionMeta.textContent = `${ens.reason || ""} · agree:${agree} · ${ens.coin || ""}`;
    renderAgents(ens.proposals || []);
  }

  function eventKey(row) {
    return [
      row.ts || "",
      row.event || "",
      row.coin || "",
      row.action || "",
      row.side || "",
      row.reason || "",
      row.fill_id || "",
      row.pnl_usd ?? "",
    ].join("|");
  }

  function remember(key) {
    if (seen.has(key)) return false;
    seen.add(key);
    if (seen.size > SEEN_CAP) {
      const drop = seen.size - SEEN_CAP;
      let i = 0;
      for (const k of seen) {
        seen.delete(k);
        i += 1;
        if (i >= drop) break;
      }
    }
    return true;
  }

  function feedBody(row) {
    if (row.event === "ensemble") {
      return `ENSEMBLE ${row.action || ""} ${row.side || ""} · ${row.reason || ""}`.trim();
    }
    if (row.event === "signal") {
      return `SIGNAL ${row.side || ""} ${row.coin || ""} · ${row.reason || ""}`.trim();
    }
    if (row.event === "fill") {
      return `FILL ${row.side || ""} ${row.coin || ""} @ ${Number(row.px || 0).toFixed(2)}`;
    }
    if (row.event === "exit") {
      return `EXIT ${row.coin || ""} pnl=${Number(row.pnl_usd || 0).toFixed(4)} · ${row.reason || ""}`;
    }
    if (row.event === "sit_out" || row.event === "blocked") {
      return `${String(row.event).toUpperCase()} ${row.coin || ""} · ${row.reason || ""}`.trim();
    }
    if (row.event === "boot") {
      return `BOOT mode=${row.mode || "?"} ensemble=${row.ensemble ?? "?"}`;
    }
    return String(row.event || "?");
  }

  function pushFeed(row) {
    if (!remember(eventKey(row))) return;
    const rowEl = document.createElement("div");
    rowEl.className = `feed-row ${row.event || ""}`;
    const tEl = document.createElement("span");
    tEl.className = "t";
    tEl.textContent = (row.ts || "").slice(11, 19) || "--:--:--";
    const bEl = document.createElement("span");
    bEl.className = "b";
    bEl.textContent = feedBody(row);
    rowEl.append(tEl, bEl);
    feed.prepend(rowEl);
    while (feed.children.length > 80) feed.removeChild(feed.lastChild);
  }

  async function getJson(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  }

  function setLinkOff(label) {
    pillAlive.textContent = label;
    pillAlive.className = "pix-pill off";
  }

  async function tick() {
    if (inFlight) return;
    inFlight = true;
    try {
      const [hb, desk, stats, ev] = await Promise.all([
        getJson("/api/heartbeat"),
        getJson("/api/desk"),
        getJson("/api/stats"),
        getJson(`/api/events?after=${after}&limit=120`),
      ]);

      if (hb.alive) {
        pillAlive.textContent = "LINK ON";
        pillAlive.className = "pix-pill on";
        pillMode.textContent = `MODE ${String(hb.mode || "?").toUpperCase()}`;
        pillMode.className = "pix-pill warn";
        pillTick.textContent = `TICK ${hb.ticks ?? "--"}`;
        pillTick.className = "pix-pill";
      } else {
        setLinkOff("LINK OFF");
        pillMode.textContent = `MODE ${String(hb.mode || "--").toUpperCase()}`;
        pillMode.className = "pix-pill";
        const age = hb.age_s != null ? `AGE ${Math.round(Number(hb.age_s))}s` : "TICK --";
        pillTick.textContent = hb.ticks != null ? `TICK ${hb.ticks} · ${age}` : age;
        pillTick.className = "pix-pill off";
      }

      document.getElementById("stat-fills").textContent = String(stats.fills ?? 0);
      document.getElementById("stat-exits").textContent = String(stats.exits ?? 0);
      document.getElementById("stat-sit").textContent = String(stats.sit_outs ?? 0);
      document.getElementById("stat-pnl").textContent = Number(stats.pnl_usd || 0).toFixed(3);

      renderDecision(desk.ensemble);
      (ev.events || []).forEach(pushFeed);
      if (typeof ev.next === "number" && ev.next >= after) {
        after = ev.next;
      }
    } catch (err) {
      setLinkOff("LINK ERR");
      console.warn(err);
    } finally {
      inFlight = false;
    }
  }

  function start() {
    tick();
    timer = window.setInterval(tick, 1000);
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      if (timer != null) {
        window.clearInterval(timer);
        timer = null;
      }
    } else if (timer == null) {
      start();
    }
  });

  start();
})();
