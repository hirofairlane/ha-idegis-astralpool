// Idegis Capturer dashboard — vanilla JS, zero deps.
// Fetches /api/idegis/{state,timeseries,activity} every 30 s and renders
// SVG charts with TFP reference bands. Period selector toggles the
// time window for the vitals charts.

const SVG_NS = "http://www.w3.org/2000/svg";
let currentHours = 24;

const $ = (id) => document.getElementById(id);

// ---- Formatters -----------------------------------------------------

const fmt = {
  num(v, dp = 2) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    const abs = Math.abs(v);
    if (abs >= 100) return v.toFixed(0);
    if (abs >= 10) return v.toFixed(1);
    return v.toFixed(dp);
  },
  withUnit(v, unit) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return `${fmt.num(v)} <span class="unit">${unit}</span>`;
  },
  rel(isoOrNull) {
    if (!isoOrNull) return "—";
    const t = new Date(isoOrNull);
    const sec = Math.max(0, (Date.now() - t.getTime()) / 1000);
    if (sec < 60) return `hace ${Math.round(sec)} s`;
    const min = sec / 60;
    if (min < 60) return `hace ${Math.round(min)} min`;
    const h = min / 60;
    if (h < 48) return `hace ${h.toFixed(1)} h`;
    return `hace ${(h / 24).toFixed(1)} d`;
  },
  abs(isoOrNull) {
    if (!isoOrNull) return "";
    const t = new Date(isoOrNull);
    return t.toLocaleString("es-ES", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
  },
};

// ---- SVG helpers ----------------------------------------------------

function svgEl(tag, attrs = {}, parent = null) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
}

function clearSVG(svg) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
}

// ---- Charts: line with reference bands ------------------------------

function drawLineChart(svg, points, opts) {
  clearSVG(svg);

  const vb = svg.viewBox.baseVal;
  const W = vb.width, H = vb.height;
  const m = { left: 40, right: 12, top: 10, bottom: 22 };
  const plotW = W - m.left - m.right;
  const plotH = H - m.top - m.bottom;

  const real = points.filter(p => p && p.v !== null && p.v !== undefined && !Number.isNaN(p.v));
  if (real.length < 2) {
    svgEl("text", {
      x: W / 2, y: H / 2, "text-anchor": "middle", class: "empty",
    }, svg).textContent = "sin datos en la ventana seleccionada";
    return;
  }

  // Determine vertical range; honour the band so the chart shows it.
  // Only *finite* band bounds count — bands use ±Infinity to mean "open
  // ended" (e.g. pH < 7.2 is bad). Folding those into the range would make
  // yMin/yMax ±Infinity, yRange Infinity, and every plotted y NaN — which
  // blanked all four vitals charts (invisible line + "—" axis labels).
  let yMin = Math.min(...real.map(p => p.v));
  let yMax = Math.max(...real.map(p => p.v));
  if (opts.bands) {
    for (const b of opts.bands) {
      if (Number.isFinite(b.min)) yMin = Math.min(yMin, b.min);
      if (Number.isFinite(b.max)) yMax = Math.max(yMax, b.max);
    }
  }
  // Pad 5%.
  const pad = (yMax - yMin) * 0.08 || 0.5;
  yMin -= pad; yMax += pad;
  const yRange = yMax - yMin || 1;

  // X range = time.
  const t0 = new Date(real[0].t).getTime();
  const t1 = new Date(real[real.length - 1].t).getTime();
  const tRange = (t1 - t0) || 1;

  // ---- Reference bands -----
  if (opts.bands) {
    for (const b of opts.bands) {
      // Open-ended bands (±Infinity) clamp to the plotted range.
      let top = Number.isFinite(b.max) ? b.max : yMax;
      let bot = Number.isFinite(b.min) ? b.min : yMin;
      top = Math.min(top, yMax); bot = Math.max(bot, yMin);
      const y = m.top + (1 - (top - yMin) / yRange) * plotH;
      const h = ((top - bot) / yRange) * plotH;
      svgEl("rect", {
        x: m.left, y, width: plotW, height: Math.max(0, h),
        class: b.cls || "band-ok",
      }, svg);
    }
  }

  // ---- Y-axis labels (4 lines) -----
  const yTicks = 4;
  for (let i = 0; i <= yTicks; i++) {
    const v = yMin + (yRange * i) / yTicks;
    const y = m.top + (1 - i / yTicks) * plotH;
    svgEl("line", {
      x1: m.left, y1: y, x2: W - m.right, y2: y, class: "grid-line",
    }, svg);
    const lbl = svgEl("text", {
      x: m.left - 6, y: y + 3, class: "axis-label", "text-anchor": "end",
    }, svg);
    lbl.textContent = fmt.num(v, 1);
  }

  // ---- X-axis time labels (3 ticks) -----
  for (let i = 0; i < 3; i++) {
    const tx = t0 + (tRange * i) / 2;
    const x = m.left + ((tx - t0) / tRange) * plotW;
    const lbl = svgEl("text", {
      x, y: H - 6, class: "axis-label", "text-anchor": i === 0 ? "start" : i === 2 ? "end" : "middle",
    }, svg);
    const d = new Date(tx);
    lbl.textContent = d.toLocaleString("es-ES", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  }

  // ---- Line path -----
  let d = "";
  let lastX = 0, lastY = 0;
  for (const p of real) {
    const x = m.left + ((new Date(p.t).getTime() - t0) / tRange) * plotW;
    const y = m.top + (1 - (p.v - yMin) / yRange) * plotH;
    d += (d === "" ? "M" : "L") + ` ${x.toFixed(1)} ${y.toFixed(1)}`;
    lastX = x; lastY = y;
  }
  svgEl("path", { d, class: "line" }, svg);
  svgEl("circle", { cx: lastX, cy: lastY, r: 3.5, class: "last-dot" }, svg);
}

// ---- Charts: activity bars -----------------------------------------

function drawActivityChart(svg, days) {
  clearSVG(svg);
  const vb = svg.viewBox.baseVal;
  const W = vb.width, H = vb.height;
  const m = { left: 36, right: 12, top: 14, bottom: 30 };
  const plotW = W - m.left - m.right;
  const plotH = H - m.top - m.bottom;

  if (!days || days.length === 0) {
    svgEl("text", { x: W / 2, y: H / 2, "text-anchor": "middle", class: "empty" }, svg)
      .textContent = "sin actividad registrada";
    return;
  }

  const maxMin = Math.max(60, ...days.map(d => d.running_minutes));
  const barW = plotW / days.length * 0.7;
  const gap = plotW / days.length * 0.3;

  // y-axis ticks
  const yTicks = 4;
  for (let i = 0; i <= yTicks; i++) {
    const v = (maxMin * i) / yTicks;
    const y = m.top + (1 - i / yTicks) * plotH;
    svgEl("line", { x1: m.left, y1: y, x2: W - m.right, y2: y, class: "grid-line" }, svg);
    const lbl = svgEl("text", {
      x: m.left - 6, y: y + 3, class: "axis-label", "text-anchor": "end",
    }, svg);
    lbl.textContent = `${v.toFixed(0)} min`;
  }

  // bars
  days.forEach((d, i) => {
    const x = m.left + i * (barW + gap) + gap / 2;
    const h = (d.running_minutes / maxMin) * plotH;
    const y = m.top + plotH - h;
    svgEl("rect", { x, y, width: barW, height: h, class: "bar", rx: 2 }, svg);

    // start markers — small circles above the bar.
    if (d.start_count > 0) {
      const cx = x + barW / 2;
      const cy = y - 6;
      svgEl("circle", { cx, cy, r: 3, class: "start-marker" }, svg);
    }

    // x-axis label every ~5 days
    if (i % 5 === 0 || i === days.length - 1) {
      const lbl = svgEl("text", {
        x: x + barW / 2,
        y: H - 8,
        class: "axis-label",
        "text-anchor": "middle",
      }, svg);
      const date = new Date(d.day);
      lbl.textContent = date.toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit" });
    }
  });
}

// ---- Refresh routines ----------------------------------------------

async function refreshSummary() {
  try {
    const r = await fetch("api/idegis/state");
    if (!r.ok) return;
    const s = await r.json();

    const online = !!s.online;
    const pill = $("online-pill");
    pill.classList.remove("is-online", "is-offline");
    pill.classList.add(online ? "is-online" : "is-offline");
    pill.textContent = online ? "ONLINE" : "OFFLINE";
    $("last-update").textContent = "actualizado " + new Date().toLocaleTimeString();

    $("polling-rate").innerHTML = fmt.withUnit(s.polling_rate_per_min_5m, "req/min");
    $("captured").textContent = s.requests_total ?? "—";
    $("rw-counts").textContent = `R: ${s.read_count ?? 0} · W: ${s.write_count ?? 0}`;
    const ageS = s.age_seconds;
    if (ageS !== null && ageS !== undefined) {
      $("seconds-since").textContent = `último req hace ${ageS < 90 ? Math.round(ageS) + " s" : (ageS / 60).toFixed(1) + " min"}`;
    } else {
      $("seconds-since").textContent = "sin lecturas";
    }

    // Vital "now" values: trusted = motor-on samples averaged over a
    // >=10 min window (falls back to raw sticky if no valid sample yet).
    // With the pump off the raw probes read a stuck floor (pH ~4.8), so we
    // never surface those — we keep the last good average and flag how
    // stale it is instead.
    const tm = s.trusted_measurements || {};
    const m = s.measurements || {};
    const winMin = Math.round((s.measurement_window_s || 600) / 60);
    const tile = (id, key, unit) => {
      const t = tm[key], r = m[key];
      const v = t?.value ?? r?.value;
      const u = t?.unit ?? r?.unit ?? unit;
      $(id).innerHTML = fmt.withUnit(v, u);
      const el = $(id);
      const stale = t?.stale_seconds;
      if (t && stale != null && stale > 180) {
        el.title = `media ${winMin} min (motor en marcha) · dato de hace ${stale < 90 ? Math.round(stale) + " s" : (stale / 60).toFixed(0) + " min"}`;
        el.classList.add("stale");
      } else if (t) {
        el.title = `media ${winMin} min · ${t.n} muestras con motor en marcha`;
        el.classList.remove("stale");
      } else {
        el.title = "valor crudo (sin muestras válidas con motor en marcha)";
        el.classList.remove("stale");
      }
    };
    tile("ph-now", "ph", "pH");
    tile("salt-now", "salinity", "g/L");
    tile("temp-now", "temperature", "°C");
    tile("prod-now", "production_percent", "%");

    // Last session. The backend snapshot uses `measurements` keyed by the
    // codec's semantic names (ph/salinity/temperature/production_percent),
    // `duration_s` and `last_ts` — keep these in sync with
    // State._snapshot_session in capturer.py.
    const ls = s.last_session_closed || s.last_session || null;
    if (ls && ls.measurements) {
      const agg = ls.measurements;
      $("ses-status").textContent = "cerrada";
      $("ses-duration").textContent = ls.duration_s
        ? `${Math.round(ls.duration_s / 60)} min` : "—";
      $("ses-writes").textContent = ls.n_writes ?? "—";
      // A metric the session never sampled directly (salinity/production are
      // reported only every few hours) is filled with the last-known value and
      // flagged `carried` by the backend — show it but mark it as such.
      const setCell = (id, k) => {
        const a = agg[k];
        const el = $(id);
        const has = a && a.avg !== undefined && a.avg !== null;
        el.textContent = has ? fmt.num(a.avg, 2) : "—";
        if (has && a.carried) {
          el.title = "último valor conocido (no medido en esta sesión)";
          el.classList.add("stale");
        } else {
          el.removeAttribute("title");
          el.classList.remove("stale");
        }
      };
      setCell("ses-ph", "ph");
      setCell("ses-salt", "salinity");
      setCell("ses-temp", "temperature");
      setCell("ses-prod", "production_percent");
      $("ses-end").textContent = ls.last_ts ? fmt.abs(ls.last_ts) : "—";
    } else {
      $("ses-status").textContent = "ninguna sesión cerrada todavía";
      ["ses-duration", "ses-writes", "ses-ph", "ses-salt", "ses-temp", "ses-prod", "ses-end"]
        .forEach(id => $(id).textContent = "—");
    }
  } catch (e) { console.warn("state fetch", e); }
}

async function refreshSeries() {
  try {
    const r = await fetch(`api/idegis/timeseries?hours=${currentHours}&points=240`);
    if (!r.ok) return;
    const s = await r.json();
    const series = s.series || {};
    drawLineChart($("chart-ph"), series.ph || [], {
      bands: [
        { min: -Infinity, max: 7.2, cls: "band-bad" },
        { min: 7.2, max: 7.8, cls: "band-ok" },
        { min: 7.8, max: Infinity, cls: "band-bad" },
      ],
    });
    drawLineChart($("chart-salt"), series.salinity || [], {
      bands: [
        { min: -Infinity, max: 1.5, cls: "band-warn" },
        { min: 1.5, max: 3.0, cls: "band-ok" },
        { min: 3.0, max: Infinity, cls: "band-warn" },
      ],
    });
    drawLineChart($("chart-temp"), series.temperature || [], {
      bands: [
        { min: 20, max: 32, cls: "band-ok" },
        { min: 32, max: 36, cls: "band-warn" },
        { min: 36, max: Infinity, cls: "band-bad" },
      ],
    });
    drawLineChart($("chart-prod"), series.production || [], {
      bands: [
        { min: 0, max: 95, cls: "band-ok" },
        { min: 95, max: Infinity, cls: "band-warn" },
      ],
    });
  } catch (e) { console.warn("series fetch", e); }
}

async function refreshActivity() {
  try {
    const r = await fetch("api/idegis/activity?days=30");
    if (!r.ok) return;
    const a = await r.json();
    drawActivityChart($("chart-activity"), a.days || []);
    $("last-start-rel").textContent = fmt.rel(a.last_start);
    $("last-start-abs").textContent = fmt.abs(a.last_start);
    $("hours-week").innerHTML = fmt.withUnit(a.total_running_hours_week, "h");
    $("hours-month").textContent = `${fmt.num(a.total_running_hours_month, 1)} h · 30 d`;
  } catch (e) { console.warn("activity fetch", e); }
}

async function refreshPumps() {
  try {
    const r = await fetch("api/idegis/pumps");
    if (!r.ok) return;
    const p = await r.json();
    const price = p.price_eur_kwh;
    $("energy-price").textContent = `${fmt.num(price, 2)} €/kWh`;

    // Current tariff period (valle/llano/punta) + price in force right now.
    const t = p.tariff;
    const periodLabel = { peak: "punta", mid: "llano", valley: "valle" };
    if (t && t.period_now) {
      $("tariff-now").textContent =
        `· ${periodLabel[t.period_now] || t.period_now} ${fmt.num(t.price_now_eur_kwh, 2)} €/kWh`;
    } else {
      $("tariff-now").textContent = "";
    }

    const SRC = {
      solar: "☀️ solar", grid: "🔌 red", idle: "—",
    };

    function fill(prefix, ch) {
      $(`${prefix}-now-w`).innerHTML = fmt.withUnit(ch.now_w, "W");
      $(`${prefix}-motor-24h`).innerHTML = fmt.withUnit(ch.motor_hours_24h, "h");
      $(`${prefix}-motor-7d`).innerHTML = fmt.withUnit(ch.motor_hours_7d, "h");
      $(`${prefix}-kwh-24h`).textContent = fmt.num(ch.kwh_24h, 2);
      $(`${prefix}-kwh-7d`).textContent = fmt.num(ch.kwh_7d, 2);
      $(`${prefix}-eur-30d`).textContent = `${fmt.num(ch.eur_30d, 2)} €`;

      // Solar split (only meaningful when a grid sensor is wired).
      const c30 = (ch.cost && ch.cost["30d"]) || null;
      const solarEl = $(`${prefix}-solar-30d`);
      const pctEl = $(`${prefix}-solar-pct`);
      if (c30 && p.grid_sensor_configured) {
        solarEl.innerHTML = fmt.withUnit(c30.solar_kwh, "kWh");
        pctEl.innerHTML = fmt.withUnit(c30.solar_pct, "%");
      } else {
        solarEl.textContent = "—";
        pctEl.textContent = "—";
      }

      const srcEl = $(`${prefix}-source`);
      srcEl.textContent = ch.source_now ? (SRC[ch.source_now] || "—") : "—";

      const stateEl = $(`${prefix}-state`);
      if (ch.switch === "on") {
        stateEl.textContent = "EN MARCHA";
        stateEl.className = "pump-state running";
      } else if (ch.switch === "off") {
        stateEl.textContent = "PARADA";
        stateEl.className = "pump-state idle";
      } else {
        stateEl.textContent = "—";
        stateEl.className = "pump-state idle";
      }
    }
    fill("pump", p.pump || {});
    fill("cleaner", p.cleaner || {});
  } catch (e) { console.warn("pumps fetch", e); }
}

async function refreshRecommendation() {
  try {
    const r = await fetch("api/idegis/recommendation");
    if (!r.ok) return;
    const x = await r.json();

    $("reco-meta").textContent =
      `${fmt.num(x.pool_volume_m3 * 1000, 0)} L · ${fmt.num(x.nominal_flow_m3_h, 1)} m³/h · célula ${fmt.num(x.cell_capacity_g_h, 0)} g/h`;
    $("reco-today").innerHTML = fmt.withUnit(x.recommended_minutes_today, "min");
    $("reco-week").innerHTML = fmt.withUnit(x.recommended_minutes_week, "min");
    $("reco-real-today").textContent = `${fmt.num(x.real_minutes_today, 0)} min`;
    $("reco-real-week").textContent = `${fmt.num(x.real_minutes_week, 0)} min`;
    $("reco-cov-today").textContent = `${fmt.num(x.coverage_today_pct, 0)} %`;
    $("reco-cov-week").textContent = `${fmt.num(x.coverage_week_pct, 0)} %`;

    $("reco-driver").textContent = x.driver === "chlorine_demand"
      ? "Limitado por producción de cloro de la célula."
      : "Limitado por turnover hidráulico mínimo.";

    // Verbose formula breakdown so the user can audit how the number
    // came out.
    const chlWin = x.driver === "chlorine_demand";
    const tempC = x.water_temperature_c ?? "—";
    const tempRow = x.apply_temp_multiplier
      ? `<div class="ff-row">
           <span>🌡️ Temp agua</span>
           <span><b>${tempC} °C</b> → multiplicador <b>${fmt.num(x.temperature_multiplier, 2)}×</b></span>
         </div>`
      : `<div class="ff-row">
           <span>🌡️ Temp agua</span>
           <span><b>${tempC} °C</b> · multiplicador desactivado (cubierta)</span>
         </div>`;
    const turnEff = x.effective_turnovers_per_day ?? x.min_turnovers_per_day;
    const turnRow = x.net_n_clean_installed
      ? `<div class="ff-row">
           <span class="${!chlWin ? 'winner' : 'loser'}">→ Turnover</span>
           <span class="${!chlWin ? 'winner' : 'loser'}"><b>${x.turnover_minutes} min</b> (${fmt.num(x.pool_volume_m3, 0)}/${fmt.num(x.nominal_flow_m3_h, 1)} × 60 × ${fmt.num(turnEff, 2)} ⇐ Net'N Clean reduce el suelo)</span>
         </div>`
      : `<div class="ff-row">
           <span class="${!chlWin ? 'winner' : 'loser'}">→ Turnover</span>
           <span class="${!chlWin ? 'winner' : 'loser'}"><b>${x.turnover_minutes} min</b> (${fmt.num(x.pool_volume_m3, 0)}/${fmt.num(x.nominal_flow_m3_h, 1)} × 60 × ${x.min_turnovers_per_day})</span>
         </div>`;
    const eduRow = x.net_n_clean_installed
      ? `<div class="ff-note">
           ℹ️ El suelo de renovación cubre el ciclado de la célula UV (cloraminas).
           Con Net'N Clean activo no hace falta margen extra para zonas muertas.
         </div>`
      : `<div class="ff-note">
           ℹ️ El suelo de renovación cubre dos cosas: ciclar el agua por la
           célula UV (destruye cloraminas) y evitar zonas muertas. Si tienes
           un sistema de barrido tipo Net'N Clean, actívalo en config para
           bajar este suelo.
         </div>`;
    $("reco-formula").innerHTML = `
      ${tempRow}
      <div class="ff-row">
        <span>💧 Demanda Cl/día</span>
        <span><b>${fmt.num(x.chlorine_demand_ppm_per_day, 1)} ppm × ${fmt.num(x.pool_volume_m3, 0)} m³ = ${fmt.num(x.daily_chlorine_demand_g, 1)} g</b></span>
      </div>
      <div class="ff-row">
        <span>⚡ Célula al ${x.target_production_pct}%</span>
        <span><b>${fmt.num(x.cell_output_g_per_min, 3)} g/min</b> (${fmt.num(x.cell_capacity_g_h, 0)} g/h × ${x.target_production_pct}/100 / 60)</span>
      </div>
      <div class="ff-row">
        <span class="${chlWin ? 'winner' : 'loser'}">→ Cloro</span>
        <span class="${chlWin ? 'winner' : 'loser'}"><b>${x.chlorine_demand_minutes} min</b> (demanda / output${x.apply_temp_multiplier ? ' × temp' : ''})</span>
      </div>
      ${turnRow}
      <div class="ff-row">
        <span>= Recomendado</span>
        <span><b>max(${x.chlorine_demand_minutes}, ${x.turnover_minutes}) = ${x.recommended_minutes_today} min/día</b></span>
      </div>
      ${eduRow}
    `;

    function paintBar(barId, pct) {
      const bar = $(barId);
      const p = Math.min(150, Math.max(0, pct));
      bar.style.width = Math.min(100, p) + "%";
      bar.classList.remove("over", "under");
      if (pct >= 95 && pct <= 120) bar.classList.add("over");
      else if (pct < 50) bar.classList.add("under");
    }
    paintBar("reco-bar-today", x.coverage_today_pct);
    paintBar("reco-bar-week", x.coverage_week_pct);
  } catch (e) { console.warn("reco fetch", e); }
}

async function refreshAll() {
  await Promise.all([
    refreshSummary(),
    refreshSeries(),
    refreshActivity(),
    refreshPumps(),
    refreshRecommendation(),
  ]);
}

// ---- Period selector -----------------------------------------------

function wirePeriodPills() {
  document.querySelectorAll(".period-pills .pill").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".period-pills .pill").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentHours = parseInt(btn.dataset.hours, 10) || 24;
      refreshSeries();
    });
  });
}

// ---- Boot ----------------------------------------------------------

window.addEventListener("DOMContentLoaded", () => {
  wirePeriodPills();
  refreshAll();
  setInterval(refreshAll, 30000);
});
