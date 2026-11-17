import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import { TripBanner } from "./cityimg";
import { ItineraryCard, cabinLabel, fdate, pkr } from "./components";
import { go } from "./router";
import { useStore } from "./store";

const SORTS = {
  cheapest: (a, b) => a.min_total_pkr - b.min_total_pkr,
  fastest: (a, b) => a.duration_min - b.duration_min,
  earliest: (a, b) => a.slices[0].departure.localeCompare(b.slices[0].departure),
};

// 2. Flight results
export default function Results() {
  const { query, results, setResults, startTrip } = useStore();
  const sig = JSON.stringify(query);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [sort, setSort] = useState("cheapest");
  const [stops, setStops] = useState("any");
  const [airlines, setAirlines] = useState([]);
  const [maxPrice, setMaxPrice] = useState(null);

  useEffect(() => {
    if (results?.sig === sig) return;
    let alive = true;
    setLoading(true); setErr("");
    api.search({
      origin: query.origin, destination: query.destination, departure_date: query.departure_date,
      return_date: query.trip_type === "round_trip" ? query.return_date : null,
      passengers: query.passengers, cabin_class: query.cabin_class,
    })
      .then((r) => { if (alive) { setResults({ sig, itineraries: r.itineraries, provider: r.provider }); setMaxPrice(null); } })
      .catch((e) => alive && setErr(e.message))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [sig]); // eslint-disable-line

  const all = results?.sig === sig ? results.itineraries : [];
  const carriers = useMemo(() => [...new Set(all.map((i) => i.owner.name))].sort(), [all]);
  const top = all.length ? Math.max(...all.map((i) => i.min_total_pkr)) : 0;
  const low = all.length ? Math.min(...all.map((i) => i.min_total_pkr)) : 0;
  const cap = maxPrice ?? top;

  const shown = all
    .filter((i) => stops === "any" || (stops === "0" ? i.stops === 0 : i.stops <= 1))
    .filter((i) => !airlines.length || airlines.includes(i.owner.name))
    .filter((i) => i.min_total_pkr <= cap)
    .sort(SORTS[sort]);

  const pick = (it) => { startTrip(it, query); go("/details"); };
  const toggle = (a) => setAirlines((l) => (l.includes(a) ? l.filter((x) => x !== a) : [...l, a]));

  const first = all[0]?.slices[0];
  const fromCity = first?.origin_city || query.origin;
  const toCity = first?.destination_city || query.destination;

  return (
    <div>
      <TripBanner city={toCity} title={`${fromCity} → ${toCity}`}
        subtitle={`${query.trip_type === "round_trip" ? "Round trip" : "One way"} · ${query.passengers} passenger${query.passengers > 1 ? "s" : ""} · ${cabinLabel(query.cabin_class)}`} />
      <div className="card row between center-v">
        <div className="muted">
          {fdate(query.departure_date)}{query.trip_type === "round_trip" && query.return_date && ` – ${fdate(query.return_date)}`}
        </div>
        <button className="ghost" onClick={() => go("/")}>Modify search</button>
      </div>
      {err && <div className="card errbox">{err}</div>}
      {loading && <div className="muted pad">Searching airlines…</div>}
      {!loading && !err && results?.sig === sig && (
        <div className="layout">
          <aside className="card filters">
            <b>Sort by</b>
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="cheapest">Cheapest</option>
              <option value="fastest">Fastest</option>
              <option value="earliest">Earliest departure</option>
            </select>
            <b>Stops</b>
            {[["any", "Any"], ["0", "Non-stop only"], ["1", "Up to 1 stop"]].map(([v, l]) => (
              <label key={v} className="check"><input type="radio" checked={stops === v} onChange={() => setStops(v)} /> {l}</label>
            ))}
            <b>Max price: {pkr(cap)}</b>
            {top > low && <input type="range" min={low} max={top} step="500" value={cap} onChange={(e) => setMaxPrice(Number(e.target.value))} />}
            <b>Airlines</b>
            {carriers.map((a) => (
              <label key={a} className="check"><input type="checkbox" checked={airlines.includes(a)} onChange={() => toggle(a)} /> {a}</label>
            ))}
            <div className="muted small">Data: {results.provider === "duffel" ? "Duffel (test mode)" : "offline demo provider"}</div>
          </aside>
          <section>
            <div className="muted pad">{shown.length} of {all.length} flights</div>
            {shown.length === 0 && <div className="card muted">No flights match your filters.</div>}
            {shown.map((it) => <ItineraryCard key={it.key} it={it} onSelect={pick} />)}
          </section>
        </div>
      )}
    </div>
  );
}
