import { AirportInput } from "./components";
import { go } from "./router";
import { useStore } from "./store";

const today = () => new Date().toISOString().slice(0, 10);

// Compact flight search form (lives in the home page hero)
export default function SearchForm() {
  const { query: q, setQuery, setResults } = useStore();
  const set = (k) => (e) => setQuery({ ...q, [k]: e.target.value });
  const round = q.trip_type === "round_trip";

  const submit = (e) => {
    e.preventDefault();
    if (!q.origin || !q.destination) return;
    setResults(null);
    go("/results");
  };
  const swap = () => setQuery({ ...q, origin: q.destination, destination: q.origin });

  return (
    <form className="search-card" onSubmit={submit}>
      <div className="search-top">
        <div className="seg-toggle">
          {[["one_way", "One-way"], ["round_trip", "Round-trip"]].map(([v, l]) => (
            <label key={v} className={q.trip_type === v ? "on" : ""}>
              <input type="radio" name="trip" checked={q.trip_type === v}
                onChange={() => setQuery({ ...q, trip_type: v, return_date: v === "one_way" ? "" : q.return_date })} />
              {l}
            </label>
          ))}
        </div>
        <div className="search-opts">
          <label>Passengers
            <input type="number" min="1" max="9" value={q.passengers}
              onChange={(e) => setQuery({ ...q, passengers: Math.max(1, Math.min(9, Number(e.target.value) || 1)) })} />
          </label>
          <label>Cabin
            <select value={q.cabin_class} onChange={set("cabin_class")}>
              <option value="economy">Economy</option>
              <option value="premium_economy">Premium economy</option>
              <option value="business">Business</option>
              <option value="first">First</option>
            </select>
          </label>
        </div>
      </div>
      <div className="search-main">
        <AirportInput label="From" value={q.origin} onChange={(v) => setQuery({ ...q, origin: v })} />
        <button type="button" className="swap" title="Swap" onClick={swap}>⇄</button>
        <AirportInput label="To" value={q.destination} onChange={(v) => setQuery({ ...q, destination: v })} />
        <label>Departure
          <input type="date" min={today()} required value={q.departure_date} onChange={set("departure_date")} />
        </label>
        {round && (
          <label>Return
            <input type="date" required min={q.departure_date || today()} value={q.return_date} onChange={set("return_date")} />
          </label>
        )}
        <button className="cta">Search flights</button>
      </div>
    </form>
  );
}
