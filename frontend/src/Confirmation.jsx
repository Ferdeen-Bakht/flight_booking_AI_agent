import { useEffect, useState } from "react";
import { api, openTicket, postForm } from "./api";
import { useAuth } from "./auth";
import { SliceView, bagText, pkr, statusLabel } from "./components";
import { TripBanner } from "./cityimg";
import { go } from "./router";

// 6. Booking confirmation
export default function Confirmation({ reference }) {
  const { user, ready, openAuth } = useAuth();
  const [b, setB] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (user) api.booking(reference).then(setB).catch((e) => setErr(e.message));
  }, [user, reference]);

  if (!ready) return <div className="muted">Loading…</div>;
  if (!user)
    return (
      <div className="card center">
        <p>Log in to view booking {reference}.</p>
        <button onClick={() => openAuth("Log in to view your booking.")}>Log in</button>
      </div>
    );
  if (err) return <div className="error">{err}</div>;
  if (!b) return <div className="muted">Loading booking…</div>;

  const pay = async () => {
    try { const { post_url, fields } = await api.initiatePayment(b.reference); postForm(post_url, fields); }
    catch (e) { setErr(e.message); }
  };
  const issued = b.ticket_status === "issued";

  const s0 = b.offer.slices[0];
  return (
    <div>
      <TripBanner city={s0.destination_city} subtitle={issued ? "Your trip is booked" : "Your booking"} title={`${s0.origin_city} → ${s0.destination_city}`} />
      <div className={`card status-card ${issued ? "good" : b.status === "cancelled" ? "bad" : "wait"}`}>
        {issued && <>
          <div className="muted">Booking confirmed 🎉</div>
          <div className="pnr">{b.pnr}</div>
          <div className="muted small">Booking reference (PNR) · our ref {b.reference}</div>
        </>}
        {!issued && b.status === "paid" && <div><h3>Payment received — ticket issuance {b.ticket_status.replace("_", " ")}</h3><div className="error">{b.note}</div></div>}
        {b.status === "pending_payment" && <div><h3>Awaiting payment</h3><button className="pay" onClick={pay}>Pay {pkr(b.amount_pkr)} with JazzCash</button></div>}
        {b.status === "payment_failed" && <div><h3>Payment failed</h3><button className="pay" onClick={pay}>Retry payment</button></div>}
        {b.status === "cancelled" && <div><h3>This booking was cancelled</h3><div className="muted small">{b.note}</div></div>}
      </div>

      <div className="card">
        <h3>Status</h3>
        <div className="grid2">
          <div><b>Payment</b><div><span className={`badge ${b.status}`}>{statusLabel(b.status)}</span></div></div>
          <div><b>Ticket</b><div><span className={`badge ${b.ticket_status}`}>{b.ticket_status.replace("_", " ")}</span></div></div>
        </div>
        {b.email_notice && <div className="ok small pad">✉ {b.email_notice}{b.mock_mailbox && " (demo mode: saved to backend/outbox/ — configure SMTP to really send)"}</div>}
      </div>

      <div className="card">
        <h3>Flight information</h3>
        {b.offer.slices.map((s, i) => <SliceView key={i} s={s} detailed label={b.offer.slices.length > 1 ? (i ? "Return" : "Outbound") : "Flight"} />)}
        <div className="muted small">{b.offer.fare_name} fare · {bagText(b.offer.baggage)}</div>
      </div>

      <div className="card">
        <h3>Passengers</h3>
        {b.passengers.map((p, i) => (
          <div key={i}>{p.title.toUpperCase()} {p.given_name} {p.family_name}
            {b.documents[i]?.number && <span className="muted small"> · ticket {b.documents[i].number}</span>}</div>
        ))}
        <div className="muted small pad">Total paid: {pkr(b.amount_pkr)}</div>
      </div>

      <div className="row gap pad">
        <button disabled={!issued} onClick={() => openTicket(b.reference).catch((e) => setErr(e.message))}>
          {issued ? "Download ticket" : "Ticket not issued yet"}
        </button>
        <button className="ghost" onClick={() => go("/trips")}>My trips</button>
        <button className="ghost" onClick={() => go("/")}>Back to assistant</button>
      </div>
    </div>
  );
}
