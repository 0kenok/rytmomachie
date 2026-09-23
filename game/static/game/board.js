(function () {
  "use strict";

  const cfg = window.RYTHMO;
  const ROWS = cfg.rows;
  const COLS = cfg.cols;
  const FILES = "abcdefgh";
  const POLL_MS = 2000;

  const boardEl = document.getElementById("board");
  const statusEl = document.getElementById("status");
  const goalEl = document.getElementById("goal");
  const logEl = document.getElementById("log");
  const capWhiteEl = document.getElementById("cap-white");
  const capBlackEl = document.getElementById("cap-black");
  const resignBtn = document.getElementById("resign");

  let state = null;
  let selected = null; // piece id
  let busy = false;
  let botPending = false;
  const BOT_MIN_DELAY_MS = 500; // so the player sees their own move land first
  let flash = "";

  const T = cfg.strings;
  const sq = (r, c) => `${FILES[c]}${r + 1}`;
  // Fill "%(name)s" placeholders, as in Django's gettext strings.
  const fmt = (template, params) =>
    template.replace(/%\((\w+)\)s/g, (m, name) => (name in params ? params[name] : m));
  const pieceName = (p) => fmt(T.piece, { side: T[p.side], shape: T[p.shape], value: p.value });

  // ---- Orientation --------------------------------------------------------

  function perspective() {
    const sides = state ? state.your_sides : [];
    return sides.length === 1 && sides[0] === "black" ? "black" : "white";
  }

  function layout() {
    const avail = boardEl.parentElement.clientWidth - 6;
    const horizontal = avail >= ROWS * 34;
    const cellsAcross = horizontal ? ROWS : COLS;
    const cell = Math.max(24, Math.min(56, Math.floor(avail / cellsAcross)));
    return { horizontal, cell };
  }

  // Engine (row, col) -> display (x, y).
  function toDisplay(r, c, horizontal, persp) {
    if (horizontal) {
      return persp === "white" ? { x: r, y: COLS - 1 - c } : { x: ROWS - 1 - r, y: c };
    }
    return persp === "white" ? { x: c, y: ROWS - 1 - r } : { x: COLS - 1 - c, y: r };
  }

  // ---- Pieces -------------------------------------------------------------

  const SVG_NS = "http://www.w3.org/2000/svg";

  function svgEl(tag, attrs) {
    const el = document.createElementNS(SVG_NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
  }

  function pieceSvg(p) {
    const svg = svgEl("svg", { viewBox: "0 0 100 100", class: `piece ${p.side}` });
    let shape;
    let textY = 50;
    let size = String(p.value).length >= 3 ? 30 : 36;
    switch (p.shape) {
      case "circle":
        shape = svgEl("circle", { cx: 50, cy: 50, r: 44 });
        break;
      case "triangle":
        shape = svgEl("polygon", { points: "50,5 96,92 4,92" });
        textY = 64;
        size -= 6;
        break;
      case "square":
        shape = svgEl("rect", { x: 7, y: 7, width: 86, height: 86, rx: 3 });
        break;
      default: // pyramid: a stepped ziggurat
        shape = svgEl("polygon", {
          points: "32,6 68,6 68,34 82,34 82,62 96,62 96,94 4,94 4,62 18,62 18,34 32,34",
        });
        textY = 60;
        size -= 4;
    }
    shape.classList.add("shape");
    svg.appendChild(shape);
    const text = svgEl("text", { x: 50, y: textY, "font-size": size });
    text.textContent = p.value;
    svg.appendChild(text);
    const title = svgEl("title", {});
    title.textContent = pieceName(p) +
      (p.layers ? ` (${p.layers.join(" + ")})` : "") + ` at ${sq(p.r, p.c)}`;
    svg.appendChild(title);
    return svg;
  }

  // ---- Rendering ----------------------------------------------------------

  function render() {
    if (!state) return;
    renderBoard();
    renderStatus();
    renderGoal();
    renderCaptured();
    renderLog();
    if (resignBtn) resignBtn.disabled = !!state.winner;
  }

  function renderBoard() {
    const { horizontal, cell } = layout();
    const persp = perspective();
    const across = horizontal ? ROWS : COLS;
    const down = horizontal ? COLS : ROWS;
    boardEl.style.setProperty("--cell", `${cell}px`);
    boardEl.style.gridTemplateColumns = `repeat(${across}, var(--cell))`;
    boardEl.textContent = "";

    const byPos = new Map(state.pieces.map((p) => [`${p.r},${p.c}`, p]));
    const moves = state.legal_moves || {};
    const targets = new Set(selected && moves[selected] ? moves[selected].map(([r, c]) => `${r},${c}`) : []);
    const last = state.log.length ? state.log[state.log.length - 1] : null;
    const lastSquares = new Set(last ? [last.from.join(","), last.to.join(",")] : []);

    const cells = new Array(across * down);
    for (let r = 0; r < ROWS; r++) {
      for (let c = 0; c < COLS; c++) {
        const { x, y } = toDisplay(r, c, horizontal, persp);
        const key = `${r},${c}`;
        const el = document.createElement("div");
        el.className = "cell" + ((r + c) % 2 ? " dark" : "");
        el.dataset.r = r;
        el.dataset.c = c;
        // Mark the line between the two halves of the board.
        if (horizontal && x === ROWS / 2) el.classList.add("half-a");
        if (!horizontal && y === ROWS / 2) el.classList.add("half-b");
        if (lastSquares.has(key)) el.classList.add("last");

        const p = byPos.get(key);
        let label = sq(r, c);
        if (p) {
          el.appendChild(pieceSvg(p));
          label += `, ${pieceName(p)}`;
          if (moves[p.id]) el.classList.add("movable");
          if (p.id === selected) el.classList.add("selected");
        }
        if (targets.has(key)) {
          el.classList.add("target");
          label += `, ${T.moveHere}`;
        }
        if (el.classList.contains("movable") || el.classList.contains("target")) {
          el.tabIndex = 0;
          el.setAttribute("role", "button");
        }
        el.setAttribute("aria-label", label);
        cells[y * across + x] = el;
      }
    }
    cells.forEach((el) => boardEl.appendChild(el));
  }

  function renderStatus() {
    statusEl.textContent = "";
    const line = document.createElement("div");
    if (state.winner) {
      line.className = "winner";
      line.textContent = fmt(T.wins, { side: T[state.winner], reason: winReason(state.win_reason) });
    } else {
      const dot = document.createElement("span");
      dot.className = `turn-dot ${state.turn}`;
      line.appendChild(dot);
      let text = fmt(T.toMove, { side: T[state.turn] });
      const mine = state.your_sides.includes(state.turn);
      if (botsTurn()) {
        text = fmt(T.withDetail, { text, detail: fmt(T.botThinking, { level: state.ai.level_name }) });
      } else if (state.your_sides.length === 1) {
        text = fmt(T.withDetail, { text, detail: mine ? T.yourTurn : T.waiting });
      } else if (!state.your_sides.length) {
        text += ` (${T.spectating})`;
      }
      line.appendChild(document.createTextNode(text));
    }
    statusEl.appendChild(line);
    if (flash) {
      const f = document.createElement("div");
      f.className = "flash";
      f.textContent = flash;
      statusEl.appendChild(f);
    }
  }

  function winReason(reason) {
    if (typeof reason === "string") return reason; // games saved before translations
    const params = { ...reason };
    let key = `reason_${reason.code}`;
    if (reason.code === "progression") {
      key += `_${reason.kind}`;
      params.values = reason.values.join(", ");
    }
    if (reason.side) params.side = T[reason.side];
    return T[key] ? fmt(T[key], params) : reason.code;
  }

  function renderGoal() {
    const w = state.captured.white;
    const b = state.captured.black;
    const sum = (list) => list.reduce((a, p) => a + p.value, 0);
    const score = state.victory === "goods"
      ? { white: sum(w), black: sum(b) }
      : { white: w.length, black: b.length };
    goalEl.textContent = fmt(T[`goal_${state.victory}`], { target: state.target, ...score });
  }

  function renderCaptured() {
    for (const [el, list] of [[capWhiteEl, state.captured.white], [capBlackEl, state.captured.black]]) {
      el.textContent = "";
      for (const p of list) {
        const chip = document.createElement("span");
        chip.className = `chip ${p.side}`;
        chip.textContent = p.value;
        chip.title = pieceName(p);
        el.appendChild(chip);
      }
    }
  }

  function renderLog() {
    logEl.textContent = "";
    for (const m of state.log) {
      const li = document.createElement("li");
      li.textContent = fmt(T.logMove, { piece: pieceName(m), from: sq(...m.from), to: sq(...m.to) });
      for (const c of m.captures) {
        const span = document.createElement("div");
        span.className = "cap";
        const taken = { side: m.side === "white" ? "black" : "white", shape: c.shape, value: c.value };
        span.textContent = "✕ " + fmt(T.took, { piece: pieceName(taken), rule: T[`rule_${c.rule}`] || c.rule }) +
          (c.detail ? ` (${c.detail})` : "");
        li.appendChild(span);
      }
      logEl.appendChild(li);
    }
    logEl.scrollTop = logEl.scrollHeight;
  }

  // ---- Server -------------------------------------------------------------

  async function fetchState() {
    const res = await fetch(`${cfg.stateUrl}?key=${encodeURIComponent(cfg.key)}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": cfg.csrfToken },
      body: JSON.stringify({ ...body, key: cfg.key }),
    });
    const data = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  function setState(next) {
    if (state && next.version !== state.version) selected = null;
    state = next;
    render();
    requestBotMove();
  }

  function botsTurn() {
    return !!(state && state.ai && !state.winner && state.turn === state.ai.side);
  }

  async function requestBotMove() {
    if (botPending || !botsTurn() || !cfg.key) return;
    botPending = true;
    try {
      const [next] = await Promise.all([
        post(cfg.botUrl, {}),
        new Promise((resolve) => setTimeout(resolve, BOT_MIN_DELAY_MS)),
      ]);
      flash = "";
      botPending = false;
      setState(next);
    } catch (err) {
      flash = err.message; // the next poll tries again
      render();
    } finally {
      botPending = false;
    }
  }

  async function sendMove(frm, to) {
    busy = true;
    try {
      flash = "";
      setState(await post(cfg.moveUrl, { from: frm, to }));
    } catch (err) {
      flash = err.message;
      selected = null;
      render();
    } finally {
      busy = false;
    }
  }

  async function poll() {
    if (busy || botPending || (state && state.winner)) return;
    try {
      const next = await fetchState();
      if (!state || next.version !== state.version) setState(next);
      else requestBotMove();
    } catch (err) {
      /* transient network errors: try again on the next tick */
    }
  }

  // ---- Input --------------------------------------------------------------

  function activate(cellEl) {
    if (!state || busy || state.winner) return;
    const r = Number(cellEl.dataset.r);
    const c = Number(cellEl.dataset.c);
    const moves = state.legal_moves || {};
    const piece = state.pieces.find((p) => p.r === r && p.c === c);

    if (selected && cellEl.classList.contains("target")) {
      const from = state.pieces.find((p) => p.id === selected);
      sendMove([from.r, from.c], [r, c]);
      return;
    }
    selected = piece && moves[piece.id] && piece.id !== selected ? piece.id : null;
    flash = "";
    render();
    if (selected) {
      const el = boardEl.querySelector(`.cell[data-r="${r}"][data-c="${c}"]`);
      if (el) el.focus();
    }
  }

  boardEl.addEventListener("click", (e) => {
    const cellEl = e.target.closest(".cell");
    if (cellEl) activate(cellEl);
  });
  boardEl.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const cellEl = e.target.closest(".cell");
    if (cellEl) {
      e.preventDefault();
      activate(cellEl);
    }
  });

  if (resignBtn) {
    resignBtn.addEventListener("click", async () => {
      if (!window.confirm(T.resignConfirm)) return;
      try {
        setState(await post(cfg.resignUrl, {}));
      } catch (err) {
        flash = err.message;
        render();
      }
    });
  }

  const copyBtn = document.getElementById("copy-invite");
  if (copyBtn) {
    copyBtn.addEventListener("click", async () => {
      const input = document.getElementById("invite");
      try {
        await navigator.clipboard.writeText(input.value);
        copyBtn.textContent = T.copied;
      } catch (err) {
        input.select();
      }
    });
  }

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(render, 100);
  });

  poll();
  setInterval(poll, POLL_MS);
})();
