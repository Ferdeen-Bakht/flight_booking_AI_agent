import { useEffect, useState } from "react";

const parse = () => window.location.hash.replace(/^#/, "") || "/";

export const go = (path) => {
  window.location.hash = path;
  window.scrollTo(0, 0);
};

export function useRoute() {
  const [path, setPath] = useState(parse());
  useEffect(() => {
    const h = () => setPath(parse());
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);
  return path;
}
