import { useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import Confirmation from "./Confirmation";
import Details from "./Details";
import Home from "./Home";
import Passengers from "./Passengers";
import Results from "./Results";
import Review from "./Review";
import Trips from "./Trips";
import { go, useRoute } from "./router";
import { useStore } from "./store";

export default function App() {
  const route = useRoute();
  const params = new URLSearchParams(window.location.search);
  const payment = params.get("payment");
  const { user, logout, openAuth } = useAuth();
  const { results, selected, passengers, lastRef, setLastRef } = useStore();
  const [mode, setMode] = useState("");
  const [meta, setMeta] = useState(null);
  const [banner, setBanner] = useState(payment ? { kind: payment, ref: params.get("ref") } : null);

  useEffect(() => {
    api.paymentMode().then((r) => setMode(r.mode)).catch(() => {});
    api.meta().then(setMeta).catch(() => {});
  }, []);

  const path = route.split("?")[0];
  const confirmRef = path.startsWith("/confirmation/") ? path.split("/")[2] : null;
  useEffect(() => { if (confirmRef) setLastRef(confirmRef); }, [confirmRef]); // eslint-disable-line

  const dismiss = () => { setBanner(null); window.history.replaceState({}, "", window.location.pathname + window.location.hash); };
  const msgs = {
    success: ["ok", (r) => `Payment successful for ${r}.`],
    failed: ["bad", (r) => `Payment failed for ${r}. You can retry below.`],
    tampered: ["bad", () => "Payment response failed hash verification and was rejected."],
    unknown: ["bad", () => "Unknown payment transaction."],
  };

  // The six booking tabs. A tab unlocks once you've reached that stage.
  const TABS = [
    { key: "home", n: 1, label: "Home", to: "/", on: true, match: (p) => p === "/" },
    { key: "results", n: 2, label: "Results", to: "/results", on: !!(results || selected), match: (p) => p === "/results" },
    { key: "details", n: 3, label: "Details", to: "/details", on: !!selected, match: (p) => p === "/details" },
    { key: "passengers", n: 4, label: "Passengers", to: "/passengers", on: !!selected, match: (p) => p === "/passengers" },
    { key: "review", n: 5, label: "Review & pay", to: "/review", on: !!(selected && passengers), match: (p) => p === "/review" },
    { key: "confirmation", n: 6, label: "Confirmation", to: lastRef ? `/confirmation/${lastRef}` : "/", on: !!lastRef, match: (p) => p.startsWith("/confirmation/") },
  ];

  let page;
  if (confirmRef) page = <Confirmation reference={confirmRef} />;
  else if (path === "/results") page = <Results />;
  else if (path === "/details") page = <Details />;
  else if (path === "/passengers") page = <Passengers />;
  else if (path === "/review") page = <Review />;
  else if (path === "/trips") page = <Trips />;
  else page = <Home />;

  return (
    <>
      <header className="topbar">
        <div className="topbar-in">
          <h1 className="logo" onClick={() => go("/")}><span>✈</span> SkyAgent</h1>
          <nav>
            <button className={path === "/" ? "active" : ""} onClick={() => go("/")}>Home</button>
            <button className={path === "/trips" ? "active" : ""} onClick={() => go("/trips")}>My trips</button>
          </nav>
          <div className="spacer" />
          {meta && <span className="mode" title="flight data source">{meta.provider === "duffel" ? "Duffel test data" : "Demo data"}</span>}
          {mode && <span className={`mode ${mode}`}>JazzCash {mode}</span>}
          {user ? (
            <div className="row gap center-v">
              <span className="avatar">{user.name[0]}</span>
              <span className="hide-sm">{user.name.split(" ")[0]}</span>
              <button className="ghost sm" onClick={logout}>Log out</button>
            </div>
          ) : (
            <div className="row gap">
              <button className="ghost sm" onClick={() => openAuth()}>Log in</button>
              <button className="sm" onClick={() => openAuth(undefined, undefined, "signup")}>Sign up</button>
            </div>
          )}
        </div>
      </header>

      <div className="app">
        <div className="tabs" role="tablist">
          {TABS.map((t) => (
            <button key={t.key} role="tab" disabled={!t.on} className={`tab ${t.match(path) ? "on" : ""}`}
              onClick={() => go(t.to)}>
              <span className="n">{t.n}</span> {t.label}
            </button>
          ))}
        </div>
        {banner && msgs[banner.kind] && (
          <div className={`banner ${msgs[banner.kind][0]}`} onClick={dismiss}>{msgs[banner.kind][1](banner.ref || "")} <u>dismiss</u></div>
        )}
        <main>{page}</main>
      </div>
    </>
  );
}
