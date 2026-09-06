(() => {
  const AGENTS = ["imbalance", "funding", "liquidity", "spread_micro"];
  let after = 0;
  const seen = new Set();

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
    el.innerHTML = `
      <h3 class="agent-name">${name.toUpperCase()}</h3>
      <p class="agent-vote">--</p>
      <p class="agent-reason">waiting</p>
    `;
    return el;
  }

  AGENTS.forEach((name) => grid.appendChild(tile(name)));

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
    const byName = Object.fromEntries((proposals || []).map((p) => [p.agent, p]));
    AGENTS.forEach((name) => {
      const el = grid.querySelector(`[data-agent="${name}"]`);
      if (!el) return;
      const p = byName[name];
      el.className = `agent ${voteClass(p?.kind, p?.side)} flash`;
      el.querySelector(".agent-vote").textContent = voteLabel(p);
      const conf = p?.confidence != null ? ` · ${Math.round(p.confidence)}` : "";
      el.querySelector(".agent-reason").textContent = `${p?.reason || "silent"}${conf}`;
      setTimeout(() => el.classList.remove("flash"), 120);
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

  function pushFeed(row) {
    const key = `${row.ts}|${row.event}|${row.coin || ""}|${row.reason || ""}|${row.fill_id || ""}`;
    if (seen.has(key)) return;
    seen.add(key);
    const rowEl = document.createElement("div");
    rowEl.className = `feed-row ${row.event || ""}`;
    const t = (row.ts || "").slice(11, 19) || "--:--:--";
    let body = row.event || "?";
    if (row.event === "ensemble") {
      body = `ENSEMBLE ${row.action} ${row.side || ""} · ${row.reason || ""}`;
    } else if (row.event === "signal") {
      body = `SIGNAL ${row.side} ${row.coin} · ${row.reason || ""}`;
    } else if (row.event === "fill") {
      body = `FILL ${row.side} ${row.coin} @ ${Number(row.px || 0).toFixed(2)}`;
    } else if (row.event === "exit") {
      body = `EXIT ${row.coin} pnl=${Number(row.pnl_usd || 0).toFixed(4)} · ${row.reason || ""}`;
    } else if (row.event === "sit_out" || row.event === "blocked") {
      body = `${row.event.toUpperCase()} ${row.coin || ""} · ${row.reason || ""}`;
    } else if (row.event === "boot") {
      body = `BOOT mode=${row.mode} ensemble=${row.ensemble}`;
    }
    rowEl.innerHTML = `<span class="t">${t}</span><span class="b">${body}</span>`;
    feed.prepend(rowEl);
    while (feed.children.length > 80) feed.removeChild(feed.lastChild);
  }

  async function getJson(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  }

  async function tick() {
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
        pillMode.textContent = `MODE ${(hb.mode || "?").toUpperCase()}`;
        pillMode.className = "pix-pill warn";
        pillTick.textContent = `TICK ${hb.ticks ?? "--"}`;
      } else {
        pillAlive.textContent = "LINK OFF";
        pillAlive.className = "pix-pill off";
      }

      document.getElementById("stat-fills").textContent = String(stats.fills ?? 0);
      document.getElementById("stat-exits").textContent = String(stats.exits ?? 0);
      document.getElementById("stat-sit").textContent = String(stats.sit_outs ?? 0);
      document.getElementById("stat-pnl").textContent = Number(stats.pnl_usd || 0).toFixed(3);

      renderDecision(desk.ensemble);
      (ev.events || []).forEach(pushFeed);
      after = ev.next ?? after;
    } catch (err) {
      pillAlive.textContent = "LINK ERR";
      pillAlive.className = "pix-pill off";
      console.warn(err);
    }
  }

  tick();
  setInterval(tick, 1000);
})();
