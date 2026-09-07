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
  const positionState = document.getElementById("position-state");
  const positionMeta = document.getElementById("position-meta");
  const feed = document.getElementById("event-feed");
  const pillAlive = document.getElementById("pill-alive");
  const pillMode = document.getElementById("pill-mode");
  const pillTick = document.getElementById("pill-tick");
  const pillKill = document.getElementById("pill-kill");
  const pillArm = document.getElementById("pill-arm");
  const pillDry = document.getElementById("pill-dry");
  const stratGrid = document.getElementById("strat-grid");

  const DEFAULT_STRATS = [
    { id: "imbalance", name: "S1 imbalance", role: "L2 book imbalance scalp", active: true },
    { id: "funding", name: "S3 funding", role: "funding extreme lean", active: false },
    { id: "liquidity", name: "liquidity gate", role: "spread/depth quality", active: false },
    { id: "spread_micro", name: "S2 spread micro", role: "tight-spread micro lean", active: false },
    { id: "risk", name: "risk gate", role: "fee/kill/cooldown veto", active: true },
  ];

  function renderStrategies(status) {
    const list = status.strategies && status.strategies.length ? status.strategies : DEFAULT_STRATS;
    const fees = `taker ${status.taker_fee_bps ?? 3.5}bps · ioc≥${status.ioc_slip_bps_min ?? 5}bps · ${status.execution_model || "hl_ioc_taker"}`;
    stratGrid.replaceChildren();
    list.forEach((s) => {
      const el = document.createElement("article");
      el.className = `strat ${s.active ? "on" : "off"}`;
      const name = document.createElement("h3");
      name.className = "strat-name";
      name.textContent = String(s.name || s.id || "?").toUpperCase();
      const role = document.createElement("p");
      role.className = "strat-role";
      role.textContent = s.role || "";
      const flag = document.createElement("p");
      flag.className = "strat-flag";
      flag.textContent = s.active ? "ON" : "OFF";
      el.append(name, role, flag);
      stratGrid.appendChild(el);
    });
    const feeEl = document.createElement("p");
    feeEl.className = "strat-fees";
    feeEl.textContent = fees;
    stratGrid.appendChild(feeEl);
  }

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

  function renderPosition(pos) {
    if (!pos || !pos.open) {
      positionState.textContent = "FLAT";
      positionState.className = "position-state flat";
      positionMeta.textContent = "No open inventory.";
      return;
    }
    const side = String(pos.side || "").toUpperCase();
    positionState.textContent = `${side} ${pos.coin || ""}`;
    positionState.className = `position-state open ${pos.side || ""}`;
    const u =
      pos.unrealized_pnl_usd != null
        ? `uPnL ${Number(pos.unrealized_pnl_usd).toFixed(4)}`
        : "uPnL --";
    const mid = pos.mark_mid != null ? `mid ${Number(pos.mark_mid).toFixed(2)}` : "mid --";
    const age = pos.age_s != null ? `age ${Math.round(Number(pos.age_s))}s` : "";
    positionMeta.textContent = `@ ${Number(pos.entry_px || 0).toFixed(2)} · ${mid} · ${u} · ${age}`.trim();
  }

  function renderStats(stats) {
    document.getElementById("stat-fills").textContent = String(stats.fills ?? 0);
    document.getElementById("stat-exits").textContent = String(stats.exits ?? 0);
    document.getElementById("stat-wl").textContent = `${stats.wins ?? 0}/${stats.losses ?? 0}`;
    document.getElementById("stat-exp").textContent = Number(stats.expectancy || 0).toFixed(3);
    document.getElementById("stat-sit").textContent = String(stats.sit_outs ?? 0);
    document.getElementById("stat-block").textContent = String(stats.blocks ?? 0);
    document.getElementById("stat-kill").textContent = String(stats.kills ?? 0);
    const pnlEl = document.getElementById("stat-pnl");
    const pnl = Number(stats.pnl_usd || 0);
    pnlEl.textContent = pnl.toFixed(3);
    pnlEl.className = `v ${pnl < 0 ? "neg" : pnl > 0 ? "pos" : ""}`;
  }

  function renderPills(hb, status) {
    if (hb.alive) {
      pillAlive.textContent = "LINK ON";
      pillAlive.className = "pix-pill on";
      pillMode.textContent = `MODE ${String(hb.mode || status.mode || "?").toUpperCase()}`;
      pillMode.className = "pix-pill warn";
      pillTick.textContent = `TICK ${hb.ticks ?? status.ticks ?? "--"}`;
      pillTick.className = "pix-pill";
    } else {
      pillAlive.textContent = "LINK OFF";
      pillAlive.className = "pix-pill off";
      pillMode.textContent = `MODE ${String(hb.mode || status.mode || "--").toUpperCase()}`;
      pillMode.className = "pix-pill";
      const age = hb.age_s != null ? `AGE ${Math.round(Number(hb.age_s))}s` : "TICK --";
      pillTick.textContent = hb.ticks != null ? `TICK ${hb.ticks} · ${age}` : age;
      pillTick.className = "pix-pill off";
    }

    const killed = Boolean(status.killed || hb.killed);
    if (killed) {
      pillKill.textContent = `KILL ${status.kill_reason || hb.kill_reason || "ON"}`
        .slice(0, 28)
        .toUpperCase();
      pillKill.className = "pix-pill off";
    } else {
      pillKill.textContent = "KILL OFF";
      pillKill.className = "pix-pill on";
    }

    if (status.armed) {
      pillArm.textContent = "ARMED";
      pillArm.className = "pix-pill warn";
    } else {
      pillArm.textContent = "DISARMED";
      pillArm.className = "pix-pill";
    }

    const dry = status.dry_run_live !== false;
    if (String(status.mode || hb.mode || "") === "live" && !dry) {
      pillDry.textContent = "LIVE POST";
      pillDry.className = "pix-pill off";
    } else {
      pillDry.textContent = dry ? "DRY RUN" : "DRY OFF";
      pillDry.className = dry ? "pix-pill on" : "pix-pill warn";
    }
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
    if (row.event === "kill") {
      return `KILL · ${row.reason || ""}`;
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

  async function tick() {
    if (inFlight) return;
    inFlight = true;
    try {
      const snap = await getJson(`/api/snapshot?after=${after}&limit=120`);
      const hb = snap.heartbeat || {};
      const status = snap.status || {};
      const stats = snap.stats || {};
      const ens = (snap.desk && snap.desk.ensemble) || null;
      const pos = snap.position || {};
      const ev = snap.events || {};

      renderPills(hb, status);
      renderStrategies(status);
      renderStats(stats);
      renderDecision(ens);
      renderPosition(pos);
      (ev.events || []).forEach(pushFeed);
      if (typeof ev.next === "number" && ev.next >= after) {
        after = ev.next;
      }
    } catch (err) {
      pillAlive.textContent = "LINK ERR";
      pillAlive.className = "pix-pill off";
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
