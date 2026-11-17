import { useAuth } from "./auth";
import { SliceView, bagText, cabinLabel, money, pkr, ruleText } from "./components";
import { TripBanner } from "./cityimg";
import { go } from "./router";
import { useStore } from "./store";

// 3. Flight details: itinerary, baggage, rules, fare comparison, final fare choice
export default function Details() {
  const { selected, setSelected, query } = useStore();
  const { user, openAuth } = useAuth();
  if (!selected) return <Empty />;
  const { itinerary: it, fareId } = selected;
  const fare = it.fares.find((f) => f.id === fareId) || it.fares[0];
  const round = it.slices.length > 1;

  const next = () => {
    if (!user) return openAuth("Log in or sign up to book this flight.", () => go("/passengers"));
    go("/passengers");
  };

  return (
    <div>
      <TripBanner city={it.slices[0].destination_city} subtitle={it.owner.name}
        title={`${it.slices[0].origin_city} → ${it.slices[0].destination_city}`} />
      <div className="card">
        <h3>Your itinerary · {it.owner.name}</h3>
        {it.slices.map((s, i) => (
          <SliceView key={i} s={s} detailed label={round ? (i === 0 ? "Outbound" : "Return") : "Flight"} />
        ))}
        <div className="muted small">{cabinLabel(fare.cabin || query.cabin_class)} · {query.passengers} passenger(s)</div>
      </div>

      <div className="card">
        <h3>Compare fares</h3>
        <div className="fares" style={{ gridTemplateColumns: `repeat(${it.fares.length}, minmax(180px, 1fr))` }}>
          {it.fares.map((f) => (
            <label key={f.id} className={`fare ${f.id === fare.id ? "on" : ""}`}>
              <input type="radio" name="fare" checked={f.id === fare.id}
                onChange={() => setSelected({ itinerary: it, fareId: f.id })} />
              <div className="fare-name">{f.fare_name}</div>
              <div className="price">{pkr(f.total_pkr)}</div>
              <div className="muted small">{money(f.total_amount, f.currency)}</div>
              <hr />
              <div className="small"><b>Baggage</b><br />{bagText(f.baggage)}</div>
              <div className="small"><b>Refund</b><br />{ruleText(f.conditions.refund, f.currency)}</div>
              <div className="small"><b>Changes</b><br />{ruleText(f.conditions.change, f.currency)}</div>
            </label>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Selected fare: {fare.fare_name}</h3>
        <div className="grid2">
          <div><b>Baggage allowance</b><div className="muted">{bagText(fare.baggage)}</div></div>
          <div><b>Cancellation / refund</b><div className="muted">{ruleText(fare.conditions.refund, fare.currency)}</div></div>
          <div><b>Date change</b><div className="muted">{ruleText(fare.conditions.change, fare.currency)}</div></div>
          <div><b>Price</b><div className="muted">{money(fare.base_amount, fare.currency)} + {money(fare.tax_amount, fare.currency)} taxes</div></div>
        </div>
        <div className="row between center-v pad">
          <div><div className="price">{pkr(fare.total_pkr)}</div><div className="muted small">total for {query.passengers} passenger(s), taxes included</div></div>
          <div className="row gap">
            <button className="ghost" onClick={() => go("/results")}>Back to results</button>
            <button onClick={next}>{user ? "Continue to passengers" : "Log in to book"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Empty() {
  return (
    <div className="card center">
      <p>No flight selected yet.</p>
      <button onClick={() => go("/")}>Search flights</button>
    </div>
  );
}
