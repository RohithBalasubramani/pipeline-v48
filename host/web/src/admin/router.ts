// admin/router.ts — the ONE routing concern: a tiny history-API router for the /admin section (the product app has
// no router by design; this stays self-contained so /admin never leaks into the prompt-shell state machine).
import { useEffect, useState } from "react";

export type Route = { section: string; rest: string[] };

export function parse(pathname: string): Route {
  const parts = pathname.replace(/^\/admin\/?/, "").split("/").filter(Boolean);
  return { section: parts[0] || "runs", rest: parts.slice(1) };
}

export function navigate(to: string) {
  const url = to.startsWith("/admin") ? to : `/admin/${to.replace(/^\//, "")}`;
  window.history.pushState(null, "", url);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.pathname));
  useEffect(() => {
    const onPop = () => setRoute(parse(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  return route;
}

export function traceHref(runId: string) {
  return `/admin/trace/${runId}`;
}
