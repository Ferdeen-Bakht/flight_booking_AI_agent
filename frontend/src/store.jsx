import { createContext, useContext, useEffect, useState } from "react";

// State lives above the pages, so switching pages/tabs never loses the chat or the booking in progress.
// It is mirrored to sessionStorage so a page refresh keeps it too.
function useStored(key, initial) {
  const [v, setV] = useState(() => {
    try {
      const s = sessionStorage.getItem(key);
      return s ? JSON.parse(s) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(v));
    } catch {
      /* storage full / unavailable: keep working in memory */
    }
  }, [key, v]);
  return [v, setV];
}

const Ctx = createContext(null);
export const useStore = () => useContext(Ctx);

const tomorrow = () => new Date(Date.now() + 86400000).toISOString().slice(0, 10);
export const defaultQuery = () => ({
  origin: "KHI", destination: "DXB", departure_date: tomorrow(), return_date: "", passengers: 1,
  cabin_class: "economy", trip_type: "one_way",
});
const WELCOME = {
  role: "assistant",
  text: "Hi! I'm SkyAgent ✈ Tell me where and when you want to fly — I can search flights, compare options and take you through booking. (Log in is only needed when you book.)",
};
const newSid = () => crypto.randomUUID();

export function StoreProvider({ children }) {
  const [sid, setSid] = useStored("chat.sid", null);
  const [msgs, setMsgs] = useStored("chat.msgs", [WELCOME]);
  const [query, setQuery] = useStored("trip.query", defaultQuery());
  const [results, setResults] = useStored("trip.results", null);      // { sig, itineraries, provider }
  const [selected, setSelected] = useStored("trip.selected", null);   // { itinerary, fareId }
  const [passengers, setPassengers] = useStored("trip.passengers", null);
  const [contact, setContact] = useStored("trip.contact", { email: "", phone: "" });
  const [lastRef, setLastRef] = useStored("trip.lastRef", null);

  useEffect(() => { if (!sid) setSid(newSid()); }, [sid, setSid]);

  const resetChat = () => { setMsgs([WELCOME]); setSid(newSid()); };
  const startTrip = (itinerary, q) => {
    setQuery({ ...q, return_date: q.return_date || "" });
    setSelected({ itinerary, fareId: itinerary.fares[0].id });
    setPassengers(null);
  };

  return (
    <Ctx.Provider value={{
      sid, msgs, setMsgs, resetChat, query, setQuery, results, setResults,
      selected, setSelected, passengers, setPassengers, contact, setContact, startTrip, lastRef, setLastRef,
    }}>
      {children}
    </Ctx.Provider>
  );
}
