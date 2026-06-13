// Pool Brain — minimal SPA. Polls /api/brain/state every 30 s.

const BAND_GROUP = {
  ok: "ok",
  warm: "warn",
  warning_low: "warn",
  warning_high: "warn",
  saturated: "warn",
  hot: "danger",
  danger_low: "danger",
  danger_high: "danger",
  unknown: "unknown",
};

function $(id) { return document.getElementById(id); }

function fmt(v, fallback = "—") {
  if (v === null || v === undefined || Number.isNaN(v)) return fallback;
  if (typeof v === "number") {
    if (Math.abs(v) >= 100) return v.toFixed(0);
    if (Math.abs(v) >= 10) return v.toFixed(1);
    return v.toFixed(2);
  }
  return v;
}

function setBand(el, value) {
  if (!el) return;
  el.textContent = value || "—";
  el.className = "band " + (value || "unknown");
}

function paintHero(score, bands) {
  $("health-score").textContent = (score === undefined || score === null) ? "—" : score;
  const subs = [];
  for (const [k, v] of Object.entries(bands || {})) {
    if (v && v !== "ok" && v !== "unknown") subs.push(`${k}: ${v}`);
  }
  $("health-sub").textContent = subs.length === 0
    ? "todo en banda 👌"
    : "ojo: " + subs.join(" · ");

  const right = $("bands");
  right.innerHTML = "";
  for (const [k, v] of Object.entries(bands || {})) {
    const group = BAND_GROUP[v] || "unknown";
    const div = document.createElement("div");
    div.className = "hero-band " + group;
    div.innerHTML = `${k}<span class="v">${v || "—"}</span>`;
    right.appendChild(div);
  }
}

function paintProgress(today, recommended) {
  const bar = $("progress-today");
  const hint = $("progress-hint");
  if (!recommended || recommended === 0) {
    bar.style.width = "0%";
    hint.textContent = "Sin recomendación calculada todavía.";
    return;
  }
  const pct = Math.min(100, (today / recommended) * 100);
  bar.style.width = pct.toFixed(1) + "%";
  if (today >= recommended) {
    hint.textContent = `✅ Ya has cubierto el recomendado de hoy (${today} min / ${recommended} min).`;
  } else {
    const left = recommended - today;
    hint.textContent = `Faltan ${left} min para cubrir el recomendado de hoy.`;
  }
}

async function refresh() {
  try {
    const r = await fetch("api/brain/state");
    if (!r.ok) return;
    const s = await r.json();
    $("ts").textContent = "actualizado " + new Date().toLocaleTimeString();

    const m = s.measurements || {};
    $("ph").textContent = fmt(m.ph);
    setBand($("ph-band"), s.bands?.ph);
    $("salt").innerHTML = `${fmt(m.salt_g_l)} <span class="unit">g/L</span>`;
    setBand($("salt-band"), s.bands?.salt);
    $("temp").innerHTML = `${fmt(m.temperature_c)} <span class="unit">°C</span>`;
    setBand($("temp-band"), s.bands?.temperature);

    $("rec-today").innerHTML = `${fmt(s.recommended_minutes_today)} <span class="unit">min</span>`;
    $("run-today").innerHTML = `${fmt(s.runtime_minutes_today)} <span class="unit">min</span>`;
    $("run-week").innerHTML = `${fmt(s.runtime_minutes_week)} <span class="unit">min</span>`;
    $("kwh-week").innerHTML = `${fmt(s.filter_kwh_week)} <span class="unit">kWh</span>`;
    paintProgress(s.runtime_minutes_today || 0, s.recommended_minutes_today || 0);

    $("pump-w").innerHTML = `${fmt(s.pump_avg_power_w)} <span class="unit">W</span>`;
    $("pump-state").textContent = (s.pump_switch || "—").toUpperCase();
    $("cleaner-w").innerHTML = `${fmt(s.cleaner_power_w)} <span class="unit">W</span>`;
    $("cleaner-state").textContent = (s.cleaner_switch || "—").toUpperCase();

    paintHero(s.health_score, s.bands);
  } catch (e) {
    console.warn("state fetch failed", e);
  }
}

async function postAction(path) {
  try {
    await fetch(path, { method: "POST" });
  } catch (e) {
    console.warn("action failed", path, e);
  }
}

window.addEventListener("DOMContentLoaded", () => {
  $("btn-stop-pump").onclick = () => {
    if (confirm("¿Parar la depuradora ahora?")) postAction("api/brain/emergency-stop/pump");
  };
  $("btn-stop-cleaner").onclick = () => {
    if (confirm("¿Parar el limpiafondos ahora?")) postAction("api/brain/emergency-stop/cleaner");
  };
  $("btn-stop-all").onclick = () => {
    if (confirm("¿Parada de emergencia GENERAL?")) postAction("api/brain/emergency-stop/all");
  };
  $("btn-report-now").onclick = () => {
    postAction("api/brain/run-report");
    alert("Reporte encolado. Llega en unos segundos por el canal configurado.");
  };
  refresh();
  setInterval(refresh, 30000);
});
