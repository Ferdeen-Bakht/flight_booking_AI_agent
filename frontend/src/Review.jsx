import { useEffect, useState } from "react";
import { api, postForm } from "./api";
import { useAuth } from "./auth";
import { SliceView, bagText, money, pkr, ruleText } from "./components";
import { Empty } from "./Details";
import { go } from "./router";
import { useStore } from "./store";

// 5. Review & payment
export default function Review() {
  const { selected, passengers, contact, query, setLastRef } = useStore();
  const { user } = useAuth();
  const [live, setLive] = useState(null);       // freshly verified offer
  const [verr, setVerr] = useState("");
  const [approved, setApproved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [ref, setRef] = useState(null);         // reuse the booking if the user retries payment

  const fareId = selected?.fareId;
  useEffect(() => {
    if (!fareId) return;
    api.offer(fareId).then(setLive).catch((e) => setVerr(e.message));
  }, [fareId]);

  if (!selected || !passengers) return <Empty />;
  if (!user) return <div className="card center"><p>Please log in to continue.</p></div>;

  const it = selected.itinerary;
  const listed = it.fares.find((f) => f.id === fareId);
  const changed = live && Math.abs(live.total_amount - listed.total_amount) > 0.005;

  const pay = async () => {
    setBusy(true); setErr("");
    try {
      let reference = ref;
      if (!reference) {
        const b = await api.book({
          offer_id: fareId, passengers, contact_email: contact.email, contact_phone: contact.phone,
          expected_total: live.total_amount, approved: true,
        });
        reference = b.reference;
        setRef(reference);
        setLastRef(reference);
      }
      const { post_url, fields } = await api.initiatePayment(reference);
      postForm(post_url, fields); // leaves the app -> JazzCash (or the mock checkout)
    } catch (e) {
      if (e.status === 409 && e.detail?.new_total) {
        setLive({ ...live, total_amount: e.detail.new_total, total_pkr: e.detail.new_pkr });
        setApproved(false);
      }
      setErr(e.message);
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="card">
        <h3>Flight summary · {it.owner.name}</h3>
        {it.slices.map((s, i) => <SliceView key={i} s={s} detailed label={it.slices.length > 1 ? (i ? "Return" : "Outbound") : "Flight"} />)}
        <div className="muted small">Fare: {listed.fare_name} · {bagText(listed.baggage)} · Refund: {ruleText(listed.conditions.refund, listed.currency)}</div>
      </div>

      <div className="card">
        <h3>Passengers</h3>
        {passengers.map((p, i) => (
          <div key={i}>{i + 1}. {p.title.toUpperCase()} {p.given_name} {p.family_name} <span className="muted small">· born {p.born_on}{p.passport_number && ` · passport ${p.passport_number}`}</span></div>
        ))}
        <div className="muted small">{contact.email} · {contact.phone}</div>
      </div>

      <div className="card">
        <h3>Price</h3>
        {verr && <div className="error">{verr} <button className="ghost" onClick={() => go("/")}>Search again</button></div>}
        {!live && !verr && <div className="muted">Verifying the final price with the airline…</div>}
        {live && (
          <>
            {changed && <div className="banner bad">The price changed since you chose this fare. Please review the new total.</div>}
            {!changed && <div className="ok small">✓ Price verified just now</div>}
            <table className="price-table">
              <tbody>
                <tr><td>Base fare ({query.passengers} pax)</td><td>{money(live.base_amount, live.currency)}</td></tr>
                <tr><td>Taxes &amp; fees</td><td>{money(live.tax_amount, live.currency)}</td></tr>
                <tr><td>Total</td><td>{money(live.total_amount, live.currency)}</td></tr>
                <tr className="total"><td>You pay (PKR)</td><td>{pkr(live.total_pkr)}</td></tr>
              </tbody>
            </table>
            {live.currency !== "PKR" && <div className="muted small">Converted from {live.currency} at the configured FX rate.</div>}
          </>
        )}
      </div>

      <div className="card">
        <h3>Payment method</h3>
        <label className="check pm"><input type="radio" checked readOnly /> <b style={{ color: "#d71920" }}>JazzCash</b> — you'll be redirected to the JazzCash sandbox checkout</label>
        <label className="check approve">
          <input type="checkbox" checked={approved} onChange={(e) => setApproved(e.target.checked)} />
          <span>I have reviewed the flights, passenger names, fare rules and total price, and I approve booking this trip and paying {live ? pkr(live.total_pkr) : "the total"}.</span>
        </label>
        {err && <div className="error">{err}</div>}
        <div className="row between pad">
          <button className="ghost" onClick={() => go("/passengers")}>Back</button>
          <button className="pay" disabled={!approved || !live || busy} onClick={pay}>
            {busy ? "Redirecting…" : `Approve & pay ${live ? pkr(live.total_pkr) : ""}`}
          </button>
        </div>
      </div>
    </div>
  );
}
