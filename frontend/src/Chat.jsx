import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";
import { BookingMini, ItineraryCard } from "./components";
import { go } from "./router";
import { useStore } from "./store";

const SUGGESTIONS = [
  "Find flights from Karachi to Dubai tomorrow",
  "Lahore to Islamabad next Friday, round trip back Sunday, 2 passengers",
  "Business class Karachi to London on 20 December",
];

// The agent is the app's starting page. All state (messages, session) lives in the store,
// so leaving this page and coming back keeps the conversation.
export default function Chat() {
  const { user, openAuth } = useAuth();
  const { sid, msgs, setMsgs, startTrip, resetChat, setQuery } = useStore();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef(null);

  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  const send = async (text) => {
    if (!text.trim() || busy || !sid) return;
    setMsgs((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const r = await api.chat(sid, text);
      setMsgs((m) => [...m, { role: "assistant", text: r.reply, ui: r.ui }]);
    } catch (e) {
      setMsgs((m) => [...m, { role: "assistant", text: "⚠ " + e.message }]);
    }
    setBusy(false);
  };

  const choose = (it, query) => {
    startTrip(it, query);
    go("/details");
  };

  return (
    <div className="chat">
      <div className="msgs">
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">{m.text}</div>
            {m.ui?.type === "offers" &&
              m.ui.itineraries.map((it) => (
                <ItineraryCard key={it.key} it={it} highlight={m.ui.highlight}
                  onSelect={(x) => choose(x, m.ui.query)} />
              ))}
            {m.ui?.type === "offers" && m.ui.itineraries.length > 1 && (
              <button className="ghost" onClick={() => { setQuery({ ...m.ui.query, return_date: m.ui.query.return_date || "" }); go("/results"); }}>See all with filters →</button>
            )}
            {m.ui?.type === "login" && !user && (
              <button onClick={() => openAuth("Log in to continue.")}>Log in / Sign up</button>
            )}
            {m.ui?.type === "booking" && <BookingMini b={m.ui.booking} />}
          </div>
        ))}
        {busy && <div className="msg assistant"><div className="bubble typing">thinking…</div></div>}
        <div ref={end} />
      </div>
      <div className="suggest">
        {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
        <button className="chip" onClick={resetChat}>↺ New chat</button>
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask the agent…" />
        <button disabled={busy}>Send</button>
      </form>
    </div>
  );
}
