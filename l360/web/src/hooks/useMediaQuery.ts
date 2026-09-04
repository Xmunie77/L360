import { useEffect, useState } from "react";

// Some layout choices can't be made in CSS — the calendar's week view swaps a
// 7-column grid for an agenda LIST on a phone, which is a render decision, not
// a style one. 820px matches the single breakpoint in theme.css.
//
// matchMedia is absent in jsdom (and in very old browsers), so every access is
// guarded: no matchMedia means "doesn't match", i.e. the desktop layout, which
// is the safe default for a grid that can side-scroll anyway.

function queryMatches(query: string): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(query).matches
    : false;
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => queryMatches(query));

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia(query);
    const onChange = () => setMatches(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, [query]);

  return matches;
}

export const MOBILE_QUERY = "(max-width: 820px)";
