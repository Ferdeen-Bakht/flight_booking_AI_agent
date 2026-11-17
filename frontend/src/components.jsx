import { useEffect, useState } from "react";
import { api } from "./api";
import { CityPhoto } from "./cityimg";

export const pkr = (n) => "PKR " + Number(n).toLocaleString();
export const money = (n, cur) => `${cur} ${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
export const hm = (iso) => iso.slice(11, 16);
export const dur = (m) => `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
export const fdate = (iso) => new Date(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
export const stopsLabel = (n) => (n === 0 ? "Non-stop" : `${n} stop${n > 1 ? "s" : ""}`);
export const cabinLabel = (c) => ({ economy: "Economy", premium_economy: "Premium economy", business: "Business", first: "First" }[c] || c);

export const ruleText = (r, cur) => {
  if (!r || r.allowed === null || r.allowed === undefined) return "Not specified by the airline";
  if (!r.allowed) return "Not allowed";
  return r.penalty ? `Allowed, fee ${money(r.penalty, r.currency || cur)}` : "Allowed, free";
};
export const bagText = (b) =>
  `${b.checked ? `${b.checked} checked bag${b.checked > 1 ? "s" : ""}` : "No checked bag"} · ${b.carry_on ? `${b.carry_on} carry-on` : "no carry-on"}`;

/** One direction of a trip: times, duration, stops and (optionally) every segment. */
export function SliceView({ s, detailed = false, label }) {
  return (
    <div className="slice">
      {label && <div className="muted small">{label} · {fdate(s.departure)}</div>}
      <div className="route">
        <div><div className="time">{hm(s.departure)}</div><div className="code">{s.origin} · {s.origin_city}</div></div>
        <div className="mid">
          <div className="muted small">{dur(s.duration_min)}</div>
          <div className="line" />
          <div className={`small ${s.stops === 0 ? "ok" : "warn"}`}>{stopsLabel(s.stops)}</div>
        </div>
        <div><div className="time">{hm(s.arrival)}{s.arrival.slice(0, 10) > s.departure.slice(0, 10) && <sup className="plus">+{Math.round((new Date(s.arrival.slice(0, 10)) - new Date(s.departure.slice(0, 10))) / 86400000)}</sup>}</div><div className="code">{s.destination} · {s.destination_city}</div></div>
      </div>
      {detailed && s.segments.map((g, i) => (
        <div key={i} className="seg">
          <div><b>{g.flight_number}</b> · {g.airline}{g.aircraft && ` · ${g.aircraft}`}</div>
          <div className="muted small">
            {g.origin} {hm(g.departing_at)} → {g.destination} {hm(g.arriving_at)} ({dur(g.duration_min)})
          </div>
          {i < s.segments.length - 1 && (
            <div className="layover small">
              Layover in {g.destination_city || g.destination}:{" "}
              {dur(Math.round((new Date(s.segments[i + 1].departing_at) - new Date(g.arriving_at)) / 60000))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/** Result card for an itinerary (used on the results page and inside the agent chat). */
export function ItineraryCard({ it, onSelect, label = "Select", highlight }) {
  const round = it.slices.length > 1;
  return (
    <div className={`card itin ${highlight ? "hl" : ""}`}>
      <CityPhoto city={it.slices[0].destination_city} width={500} className="itin-photo">
        <span className="photo-tag">{it.slices[0].destination_city}</span>
      </CityPhoto>
      <div className="itin-main">
        <div className="airline">{it.owner.name}{it.owner.iata && ` (${it.owner.iata})`}</div>
        {it.slices.map((s, i) => (
          <SliceView key={i} s={s} label={round ? (i === 0 ? "Outbound" : "Return") : null} />
        ))}
      </div>
      <div className="itin-side">
        <div className="muted small">from</div>
        <div className="price">{pkr(it.min_total_pkr)}</div>
        <div className="muted small">{it.fares.length} fare{it.fares.length > 1 ? "s" : ""}</div>
        {onSelect && <button onClick={() => onSelect(it)}>{label}</button>}
      </div>
    </div>
  );
}

export function AirportInput({ label, value, onChange }) {
  // Custom dropdown: click shows every airport, typing filters, picking sets the IATA code.
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [fetched, setFetched] = useState({ q: "", list: [] });
  const [names, setNames] = useState({});

  useEffect(() => {
    const t = setTimeout(() => {
      api.airports(q.trim()).then((r) => {
        setFetched({ q: q.trim(), list: r });
        setNames((n) => ({ ...n, ...Object.fromEntries(r.map((a) => [a.iata, a.city])) }));
      }).catch(() => {});
    }, open ? 150 : 0);
    return () => clearTimeout(t);
  }, [q, open]);

  // Until the server answers for the current text, filter the previous list locally so typing feels instant.
  const ql = q.trim().toLowerCase();
  const opts = fetched.q === q.trim() || !ql ? fetched.list
    : fetched.list.filter((a) => `${a.iata} ${a.city} ${a.name || ""}`.toLowerCase().includes(ql));
  const pick = (a) => { onChange(a.iata); setOpen(false); setQ(""); };
  const shown = open ? q : names[value] ? `${names[value]} (${value})` : value;
  const close = () => {
    // typed a raw 3-letter code that isn't in the list? accept it
    if (open && /^[A-Za-z]{3}$/.test(q.trim()) && !opts.length) onChange(q.trim().toUpperCase());
    setOpen(false); setQ("");
  };

  return (
    <label className="ap">{label}
      <input value={shown} placeholder="City or airport" autoComplete="off"
        onFocus={(e) => { setOpen(true); setQ(""); e.target.select(); }}
        onChange={(e) => setQ(e.target.value)} onBlur={close}
        onKeyDown={(e) => { if (e.key === "Enter" && open && opts[0]) { e.preventDefault(); pick(opts[0]); } }} />
      {open && (
        <div className="ap-list">
          {opts.length === 0 && <div className="ap-empty">No airports found</div>}
          {opts.map((a) => (
            <div key={a.iata} className={`ap-item ${a.iata === value ? "on" : ""}`}
              onMouseDown={(e) => { e.preventDefault(); pick(a); }}>
              <b>{a.iata}</b><span>{a.city}{a.name && a.name !== a.city ? ` – ${a.name}` : ""}</span>
              <em>{a.country}</em>
            </div>
          ))}
        </div>
      )}
    </label>
  );
}

const STATUS_LABEL = { pending_payment: "awaiting payment", payment_failed: "payment failed", paid: "paid", cancelled: "cancelled" };
export const statusLabel = (s) => STATUS_LABEL[s] || s;

export function BookingMini({ b }) {
  const o = b.offer;
  return (
    <div className="card">
      <div className="row between">
        <b>{b.reference}{b.pnr && ` · PNR ${b.pnr}`}</b>
        <span className={`badge ${b.status}`}>{statusLabel(b.status)}</span>
      </div>
      {o.slices.map((s, i) => (
        <div key={i} className="muted">{s.origin} → {s.destination} · {fdate(s.departure)} {hm(s.departure)}</div>
      ))}
      <div className="muted small">{pkr(b.amount_pkr)} · ticket: {b.ticket_status.replace("_", " ")}</div>
    </div>
  );
}
