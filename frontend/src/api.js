export const getToken = () => localStorage.getItem("token");

async function raw(path, opts = {}) {
  const t = getToken();
  const headers = { ...(opts.headers || {}), ...(t ? { Authorization: `Bearer ${t}` } : {}) };
  return fetch(path, { ...opts, headers });
}

async function req(path, opts) {
  const r = await raw(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    const msg = Array.isArray(d) ? d.map((x) => x.msg).join("; ") : typeof d === "object" && d ? d.message : d;
    throw Object.assign(new Error(msg || `Request failed (${r.status})`), { status: r.status, detail: d });
  }
  return data;
}
const json = (body, method = "POST") => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  meta: () => req("/api/meta"),
  airports: (q = "") => req(`/api/airports?q=${encodeURIComponent(q)}`),
  search: (q) => req("/api/flights/search", json(q)),
  offer: (id) => req(`/api/offers/${id}`),
  signup: (b) => req("/api/auth/signup", json(b)),
  login: (b) => req("/api/auth/login", json(b)),
  me: () => req("/api/auth/me"),
  book: (b) => req("/api/bookings", json(b)),
  bookings: () => req("/api/bookings"),
  booking: (ref) => req(`/api/bookings/${ref}`),
  cancel: (ref) => req(`/api/bookings/${ref}/cancel`, { method: "POST" }),
  profiles: () => req("/api/profiles"),
  addProfile: (p) => req("/api/profiles", json(p)),
  deleteProfile: (id) => req(`/api/profiles/${id}`, { method: "DELETE" }),
  chat: (session_id, message) => req("/api/chat", json({ session_id, message })),
  initiatePayment: (reference) => req("/api/payments/jazzcash/initiate", json({ reference })),
  paymentMode: () => req("/api/payments/config"),
};

// The ticket endpoint needs the Authorization header, so fetch it and open as a blob.
export async function openTicket(ref) {
  const r = await raw(`/api/bookings/${ref}/ticket`);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || "Ticket not available");
  const url = URL.createObjectURL(new Blob([await r.text()], { type: "text/html" }));
  window.open(url, "_blank");
}

// JazzCash hosted checkout = the browser must POST a form to their URL.
export function postForm(url, fields) {
  const f = document.createElement("form");
  f.method = "POST";
  f.action = url;
  Object.entries(fields).forEach(([k, v]) => {
    const i = document.createElement("input");
    i.type = "hidden";
    i.name = k;
    i.value = v;
    f.appendChild(i);
  });
  document.body.appendChild(f);
  f.submit();
}
