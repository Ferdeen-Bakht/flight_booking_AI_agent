import { useEffect, useState } from "react";

// City photos come from Wikipedia's public REST API (lead image of the city article).
// They're cached in memory + localStorage; if anything fails we show a coloured gradient instead.
const TITLES = { "New York": "New_York_City", "Kuala Lumpur": "Kuala_Lumpur", "Abu Dhabi": "Abu_Dhabi" };
const mem = new Map(); // city -> thumbnail url | "" (known missing)

const read = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k, v) => { try { localStorage.setItem(k, v); } catch { /* ignore */ } };

// Wikimedia thumbs can be re-sized by changing the "NNNpx-" part of the URL
const sized = (src, width) => src.replace(/\?.*$/, "").replace(/\/\d+px-/, `/${width}px-`);

export function useCityImage(city, width = 500) {
  const [src, setSrc] = useState(() => (city && mem.get(city)) || "");
  useEffect(() => {
    if (!city) return;
    if (mem.has(city)) { setSrc(mem.get(city)); return; }
    const cached = read("cityimg:v1:" + city);
    if (cached !== null) { mem.set(city, cached); setSrc(cached); return; }
    let alive = true;
    const title = TITLES[city] || city.replace(/ /g, "_");
    fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => {
        let s = j?.thumbnail?.source || "";
        if (/\.svg/i.test(s)) s = ""; // flags/maps look bad as backgrounds
        mem.set(city, s);
        write("cityimg:v1:" + city, s);
        if (alive) setSrc(s);
      })
      .catch(() => alive && setSrc(""));
    return () => { alive = false; };
  }, [city]);
  return src ? sized(src, width) : "";
}

const hue = (s = "") => [...s].reduce((a, c) => (a * 31 + c.charCodeAt(0)) % 360, 7);

/** A background photo of a city with a graceful gradient fallback. Children render on top. */
export function CityPhoto({ city, width = 500, className = "", children, onClick }) {
  const url = useCityImage(city, width);
  const h = hue(city);
  const style = {
    backgroundImage: url
      ? `url("${url}")`
      : `linear-gradient(135deg, hsl(${h} 70% 42%), hsl(${(h + 50) % 360} 70% 30%))`,
  };
  return (
    <div className={`photo ${className}`} style={style} onClick={onClick} role={onClick ? "button" : undefined}>
      {children}
    </div>
  );
}

export function TripBanner({ city, title, subtitle }) {
  return (
    <CityPhoto city={city} width={1280} className="trip-banner">
      <div className="photo-text">
        <div className="muted-w">{subtitle}</div>
        <h2>{title}</h2>
      </div>
    </CityPhoto>
  );
}
