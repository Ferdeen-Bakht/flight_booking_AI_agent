import { useState } from "react";
import Chat from "./Chat";
import { CityPhoto } from "./cityimg";
import SearchForm from "./Search";
import { useStore } from "./store";

const HERO = ["Dubai", "London", "Istanbul", "Singapore", "New York"];
const DESTS = [
  ["Dubai", "DXB", "United Arab Emirates"], ["London", "LHR", "United Kingdom"],
  ["Istanbul", "IST", "Türkiye"], ["Singapore", "SIN", "Singapore"],
  ["Doha", "DOH", "Qatar"], ["Jeddah", "JED", "Saudi Arabia"],
  ["New York", "JFK", "United States"], ["Kuala Lumpur", "KUL", "Malaysia"],
  ["Lahore", "LHE", "Pakistan"], ["Islamabad", "ISB", "Pakistan"],
];

// Home = search + assistant + inspiration, all on one page
export default function Home() {
  const { query, setQuery } = useStore();
  const [hero] = useState(() => HERO[Math.floor(Math.random() * HERO.length)]);

  const pickDestination = (code) => {
    setQuery({ ...query, destination: code, origin: query.origin === code ? "KHI" : query.origin });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div>
      <CityPhoto city={hero} width={1280} className="hero">
        <div className="hero-inner">
          <h1>Where will you fly next?</h1>
          <p>Search flights yourself, or just tell SkyAgent what you need.</p>
          <SearchForm />
        </div>
        <div className="hero-credit">📍 {hero}</div>
      </CityPhoto>

      <div className="home-grid">
        <section className="assistant card">
          <div className="assistant-head">
            <span className="bot">🤖</span>
            <div><b>Ask SkyAgent</b><div className="muted small">Your AI travel assistant — search, compare, then pick a flight to book</div></div>
          </div>
          <Chat />
        </section>

        <section>
          <h3 className="section-title">Popular destinations</h3>
          <div className="dest-grid">
            {DESTS.map(([city, code, country]) => (
              <CityPhoto key={code} city={city} className="dest" onClick={() => pickDestination(code)}>
                <div className="photo-text">
                  <b>{city}</b>
                  <span>{country}</span>
                </div>
              </CityPhoto>
            ))}
          </div>
          <div className="muted small credit">City photos from Wikipedia / Wikimedia Commons.</div>
        </section>
      </div>
    </div>
  );
}
