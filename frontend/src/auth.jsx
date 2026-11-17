import { createContext, useContext, useEffect, useState } from "react";
import { api, getToken } from "./api";

const Ctx = createContext(null);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(!getToken());
  const [modal, setModal] = useState(null); // null | { mode: "login"|"signup", reason?: string, onDone?: fn }

  useEffect(() => {
    if (!getToken()) return;
    api.me().then(setUser).catch(() => localStorage.removeItem("token")).finally(() => setReady(true));
  }, []);

  const accept = (r) => {
    localStorage.setItem("token", r.token);
    setUser(r.user);
    const cb = modal?.onDone;
    setModal(null);
    cb?.(r.user);
  };
  const logout = () => { localStorage.removeItem("token"); setUser(null); };
  // openAuth(reason, onDone): onDone runs after a successful login so a pending action can resume
  const openAuth = (reason, onDone, mode = "login") => setModal({ mode, reason, onDone });

  return (
    <Ctx.Provider value={{ user, ready, logout, openAuth }}>
      {children}
      {modal && <AuthModal modal={modal} setModal={setModal} accept={accept} />}
    </Ctx.Provider>
  );
}

function AuthModal({ modal, setModal, accept }) {
  const signup = modal.mode === "signup";
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      accept(signup ? await api.signup(f) : await api.login({ email: f.email, password: f.password }));
    } catch (e) { setErr(e.message); setBusy(false); }
  };

  return (
    <div className="overlay" onClick={() => setModal(null)}>
      <form className="card modal form1" onClick={(e) => e.stopPropagation()} onSubmit={submit}>
        <h2>{signup ? "Create account" : "Log in"}</h2>
        {modal.reason && <div className="muted">{modal.reason}</div>}
        {signup && <label>Full name<input required minLength={2} value={f.name} onChange={set("name")} /></label>}
        <label>Email<input required type="email" value={f.email} onChange={set("email")} /></label>
        <label>Password{signup && " (min 8 characters)"}
          <input required type="password" minLength={signup ? 8 : 1} value={f.password} onChange={set("password")} /></label>
        {err && <div className="error">{err}</div>}
        <button disabled={busy}>{signup ? "Sign up" : "Log in"}</button>
        <div className="muted center">
          {signup ? "Already have an account? " : "New here? "}
          <a href="#" onClick={(e) => { e.preventDefault(); setErr(""); setModal({ ...modal, mode: signup ? "login" : "signup" }); }}>
            {signup ? "Log in" : "Sign up"}
          </a>
        </div>
      </form>
    </div>
  );
}
