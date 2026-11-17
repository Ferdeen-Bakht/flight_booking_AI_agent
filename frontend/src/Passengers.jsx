import { useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import { Empty } from "./Details";
import { go } from "./router";
import { useStore } from "./store";
import { blankPassenger, validateContact, validatePassenger } from "./validate";

// 4. Passenger details (login required)
export default function Passengers() {
  const { selected, query, passengers, setPassengers, contact, setContact } = useStore();
  const { user, ready, openAuth } = useAuth();
  const [list, setList] = useState(() =>
    passengers?.length === query.passengers ? passengers : Array.from({ length: query.passengers }, blankPassenger));
  const [c, setC] = useState({ email: contact.email || "", phone: contact.phone || "" });
  const [profiles, setProfiles] = useState([]);
  const [errs, setErrs] = useState([]);

  useEffect(() => {
    if (user) {
      api.profiles().then(setProfiles).catch(() => {});
      setC((x) => ({ ...x, email: x.email || user.email }));
    }
  }, [user]);

  if (!selected) return <Empty />;
  if (!ready) return <div className="muted">Loading…</div>;
  if (!user)
    return (
      <div className="card center">
        <p>Please log in to enter passenger details and book.</p>
        <button onClick={() => openAuth("Log in or sign up to book.")}>Log in / Sign up</button>
      </div>
    );

  const it = selected.itinerary;
  const passportRequired = it.passport_required;
  const lastDep = it.slices[it.slices.length - 1].departure;
  const upd = (i, k, v) => setList((l) => l.map((p, j) => (j === i ? { ...p, [k]: v } : p)));
  const fill = (i, id) => {
    const p = profiles.find((x) => String(x.id) === id);
    if (p) setList((l) => l.map((x, j) => (j === i ? {
      ...blankPassenger(), title: p.title, gender: p.gender, given_name: p.given_name, family_name: p.family_name,
      born_on: p.born_on, passport_number: p.passport_number, passport_country: p.passport_country || "PK",
      passport_expiry: p.passport_expiry,
    } : x)));
  };

  const submit = (e) => {
    e.preventDefault();
    const all = [...list.flatMap((p, i) => validatePassenger(p, i, passportRequired, lastDep)), ...validateContact(c)];
    setErrs(all);
    if (all.length) return window.scrollTo(0, 0);
    setPassengers(list);
    setContact(c);
    go("/review");
  };

  return (
    <form onSubmit={submit}>
      {errs.length > 0 && <div className="card errbox">{errs.map((x) => <div key={x}>• {x}</div>)}</div>}
      {passportRequired && <div className="card muted small">This is an international trip: passport details are required. Enter names exactly as on the passport.</div>}
      {list.map((p, i) => (
        <div className="card" key={i}>
          <div className="row between center-v">
            <h3>Passenger {i + 1}</h3>
            {profiles.length > 0 && (
              <select defaultValue="" onChange={(e) => fill(i, e.target.value)} className="autosel">
                <option value="" disabled>Use saved passenger…</option>
                {profiles.map((x) => <option key={x.id} value={x.id}>{x.given_name} {x.family_name}</option>)}
              </select>
            )}
          </div>
          <div className="form">
            <label>Title
              <select value={p.title} onChange={(e) => upd(i, "title", e.target.value)}>
                {["mr", "ms", "mrs", "miss", "dr"].map((t) => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
              </select>
            </label>
            <label>Gender
              <select value={p.gender} onChange={(e) => upd(i, "gender", e.target.value)}>
                <option value="m">Male</option><option value="f">Female</option>
              </select>
            </label>
            <label>First name<input value={p.given_name} onChange={(e) => upd(i, "given_name", e.target.value)} required /></label>
            <label>Last name<input value={p.family_name} onChange={(e) => upd(i, "family_name", e.target.value)} required /></label>
            <label>Date of birth<input type="date" max={new Date().toISOString().slice(0, 10)} value={p.born_on} onChange={(e) => upd(i, "born_on", e.target.value)} required /></label>
            {passportRequired && (
              <>
                <label>Passport number<input value={p.passport_number} onChange={(e) => upd(i, "passport_number", e.target.value.toUpperCase())} required /></label>
                <label>Issuing country (2 letters)<input maxLength={2} value={p.passport_country} onChange={(e) => upd(i, "passport_country", e.target.value.toUpperCase())} required /></label>
                <label>Passport expiry<input type="date" value={p.passport_expiry} onChange={(e) => upd(i, "passport_expiry", e.target.value)} required /></label>
              </>
            )}
          </div>
        </div>
      ))}
      <div className="card">
        <h3>Contact details</h3>
        <div className="form">
          <label>Email (confirmation is sent here)<input type="email" value={c.email} onChange={(e) => setC({ ...c, email: e.target.value })} required /></label>
          <label>Phone (international format)<input value={c.phone} placeholder="+923001234567" onChange={(e) => setC({ ...c, phone: e.target.value.replace(/[^\d+]/g, "") })} required /></label>
        </div>
      </div>
      <div className="row between pad">
        <button type="button" className="ghost" onClick={() => go("/details")}>Back</button>
        <button>Continue to review</button>
      </div>
    </form>
  );
}
