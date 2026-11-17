import { useEffect, useState } from "react";
import { api, postForm } from "./api";
import { useAuth } from "./auth";
import { fdate, hm, pkr, statusLabel } from "./components";
import { go } from "./router";
import { blankPassenger } from "./validate";

function Trip({ b, onChange }) {
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const o = b.offer;
  const payable = b.status === "pending_payment" || b.status === "payment_failed";
  const live = b.status !== "cancelled" && !(b.status === "paid" && b.ticket_status === "cancelled");

  const cancel = async () => {
    if (!confirm(`Cancel booking ${b.reference}?`)) return;
    setBusy(true); setErr("");
    try { onChange(await api.cancel(b.reference)); } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const pay = async () => {
    try { const { post_url, fields } = await api.initiatePayment(b.reference); postForm(post_url, fields); }
    catch (e) { setErr(e.message); }
  };

  return (
    <div className="card">
      <div className="row between">
        <b>{o.slices.map((s) => `${s.origin} → ${s.destination}`).join("  ·  ")}</b>
        <span className={`badge ${b.status}`}>{statusLabel(b.status)}</span>
      </div>
      <div className="muted">{fdate(o.slices[0].departure)} {hm(o.slices[0].departure)} · {o.owner.name} · {o.fare_name}</div>
      <div className="muted small">
        {b.reference}{b.pnr && ` · PNR ${b.pnr}`} · {b.passengers.length} pax · {pkr(b.amount_pkr)} · ticket {b.ticket_status.replace("_", " ")}
      </div>
      {b.note && <div className="muted small">{b.note}</div>}
      {err && <div className="error">{err}</div>}
      <div className="row gap">
        <button className="ghost" onClick={() => go(`/confirmation/${b.reference}`)}>View</button>
        {payable && <button className="pay" onClick={pay}>Pay now</button>}
        {live && <button className="ghost" disabled={busy} onClick={cancel}>Cancel booking</button>}
      </div>
    </div>
  );
}

function Profiles() {
  const [list, setList] = useState([]);
  const [f, setF] = useState({ ...blankPassenger() });
  const [adding, setAdding] = useState(false);
  const [err, setErr] = useState("");
  const load = () => api.profiles().then(setList).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const save = async (e) => {
    e.preventDefault(); setErr("");
    try { await api.addProfile(f); setF(blankPassenger()); setAdding(false); load(); } catch (e) { setErr(e.message); }
  };
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  return (
    <div>
      <div className="row between center-v"><h3 className="section">Passenger profiles</h3>
        <button className="ghost" onClick={() => setAdding(!adding)}>{adding ? "Close" : "+ Add passenger"}</button></div>
      {list.length === 0 && !adding && <div className="muted">No saved passengers. Save them here to re-use when booking.</div>}
      {list.map((p) => (
        <div key={p.id} className="card row between center-v">
          <div>{p.title.toUpperCase()} {p.given_name} {p.family_name}<div className="muted small">born {p.born_on}{p.passport_number && ` · passport ${p.passport_number}`}</div></div>
          <button className="ghost" onClick={() => api.deleteProfile(p.id).then(load)}>Delete</button>
        </div>
      ))}
      {adding && (
        <form className="card form" onSubmit={save}>
          <label>Title<select value={f.title} onChange={set("title")}>{["mr", "ms", "mrs", "miss", "dr"].map((t) => <option key={t}>{t}</option>)}</select></label>
          <label>Gender<select value={f.gender} onChange={set("gender")}><option value="m">Male</option><option value="f">Female</option></select></label>
          <label>First name<input required value={f.given_name} onChange={set("given_name")} /></label>
          <label>Last name<input required value={f.family_name} onChange={set("family_name")} /></label>
          <label>Date of birth<input required type="date" value={f.born_on} onChange={set("born_on")} /></label>
          <label>Passport no. (optional)<input value={f.passport_number} onChange={(e) => setF({ ...f, passport_number: e.target.value.toUpperCase() })} /></label>
          <label>Passport country<input maxLength={2} value={f.passport_country} onChange={(e) => setF({ ...f, passport_country: e.target.value.toUpperCase() })} /></label>
          <label>Passport expiry<input type="date" value={f.passport_expiry} onChange={set("passport_expiry")} /></label>
          {err && <div className="error">{err}</div>}
          <button>Save passenger</button>
        </form>
      )}
    </div>
  );
}

// 7. My trips / dashboard
export default function Trips() {
  const { user, ready, openAuth } = useAuth();
  const [list, setList] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (user) api.bookings().then(setList).catch((e) => setErr(e.message));
    else setList(null);
  }, [user]);

  if (!ready) return <div className="muted">Loading…</div>;
  if (!user)
    return (
      <div className="card center">
        <p>Log in to see your trips.</p>
        <button onClick={() => openAuth("Log in to view your trips.")}>Log in</button>
      </div>
    );

  const update = (nb) => setList((l) => l.map((b) => (b.reference === nb.reference ? nb : b)));
  const now = new Date().toISOString().slice(0, 16);
  const upcoming = (list || []).filter((b) => b.status !== "cancelled" && b.departure >= now);
  const previous = (list || []).filter((b) => !upcoming.includes(b));

  return (
    <div>
      {err && <div className="error">{err}</div>}
      <h3 className="section">Upcoming flights</h3>
      {list && upcoming.length === 0 && <div className="muted">Nothing upcoming. <a href="#/">Find a flight</a></div>}
      {upcoming.map((b) => <Trip key={b.reference} b={b} onChange={update} />)}
      <h3 className="section">Previous &amp; cancelled</h3>
      {list && previous.length === 0 && <div className="muted">No previous bookings.</div>}
      {previous.map((b) => <Trip key={b.reference} b={b} onChange={update} />)}
      <Profiles />
    </div>
  );
}
