import { useEffect, useRef, useState } from "react";

import { copilotSuggest, type Suggest } from "../api";

/** Chip-prefill signal: bumping `n` re-seeds the bar with `text` (sets value, focuses, fetches). */
export type Seed = { text: string; n: number };

// shared chrome icons (ONE source — components/icons)
import { Spark, Return, Mag } from "./icons";

export function PromptBar({
  onRun,
  loading,
  seed,
}: {
  onRun: (prompt: string) => void;
  loading: boolean;
  seed?: Seed;
}) {
  // `value` = what the input shows (may be a previewed suggestion while arrowing)
  // `typed` = the text the user actually typed (restored on Escape / used for ghost)
  const [value, setValue] = useState("");
  const [typed, setTyped] = useState("");
  const [ghost, setGhost] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [active, setActive] = useState(-1);
  const [open, setOpen] = useState(false);
  const [lat, setLat] = useState<number | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const ghostRef = useRef<HTMLDivElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const ctrl = useRef<AbortController | null>(null);
  const seq = useRef(0);
  const blurT = useRef<number | undefined>(undefined);
  const lastFull = useRef("");   // last full completion (autofill or top suggestion) backing the ghost
  const cache = useRef<Map<string, Suggest>>(new Map());  // client-side per-prefix cache (instant on revisit)

  // ghost = the tail of any known completion that continues `t` (case-insensitive)
  const ghostFor = (t: string, autofill: string, sugg: string[]) => {
    const lt = t.toLowerCase();
    const cands = [autofill, ...sugg].filter(Boolean);
    const hit = cands.find((c) => c.toLowerCase().startsWith(lt) && c.length > t.length);
    return hit || "";
  };

  // debounced copilot fetch (160ms), with stale-response guard
  const fetchSoon = (text: string) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => runFetch(text), 160);
  };

  const apply = (text: string, d: Suggest) => {
    const full = ghostFor(text, d.autofill || "", d.suggestions || []);
    lastFull.current = full;
    setGhost(full ? full.slice(text.length) : "");
    setSuggestions(d.suggestions || []);
    setActive(-1);
    setLat(typeof d.latency_ms === "number" ? d.latency_ms : null);
    setOpen(true);
  };

  async function runFetch(text: string) {
    if (!text.trim()) {
      lastFull.current = ""; setGhost(""); setSuggestions([]); setActive(-1); setLat(null); return;
    }
    const hit = cache.current.get(text);   // client cache — instant, no network
    if (hit) { apply(text, hit); return; }
    ctrl.current?.abort();
    ctrl.current = new AbortController();
    const my = ++seq.current;
    try {
      const d: Suggest = await copilotSuggest(text, ctrl.current.signal);
      if (cache.current.size > 300) cache.current.clear();
      cache.current.set(text, d);
      if (my !== seq.current) return; // a newer keystroke superseded this
      apply(text, d);
    } catch (e: any) {
      if (e?.name !== "AbortError") { /* keep current ghost; don't blank on transient error */ }
    }
  }

  useEffect(() => () => { window.clearTimeout(timer.current); ctrl.current?.abort(); }, []);

  // chip prefill — when a suggested command is clicked, seed the bar (set text, focus, fetch) but do NOT auto-run
  useEffect(() => {
    if (!seed || !seed.text) return;
    setTyped(seed.text); setValue(seed.text); setGhost(""); setActive(-1);
    inputRef.current?.focus();
    fetchSoon(seed.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seed?.n]);

  const onChange = (t: string) => {
    setTyped(t); setValue(t); setActive(-1);
    // optimistic ghost: keep showing the last completion if it still continues `t`
    const lf = lastFull.current;
    setGhost(lf && t && lf.toLowerCase().startsWith(t.toLowerCase()) && lf.length > t.length
      ? lf.slice(t.length) : "");
    fetchSoon(t);
  };

  const acceptGhost = () => {
    const nv = typed + ghost;
    setTyped(nv); setValue(nv); setGhost(""); setActive(-1); fetchSoon(nv);
  };

  const moveActive = (dir: 1 | -1) => {
    if (!suggestions.length) return;
    let na = active + dir;
    if (na < -1) na = suggestions.length - 1;       // wrap up to last
    if (na >= suggestions.length) na = -1;          // wrap past bottom back to typed
    setActive(na);
    if (na === -1) { setValue(typed); } else { setValue(suggestions[na]); setGhost(""); }
  };

  const submit = (q?: string) => {
    const p = (q ?? value).trim();
    if (p && !loading) {
      // stop any pending/in-flight copilot fetch so a late response can't re-open the dropdown
      window.clearTimeout(timer.current);
      ctrl.current?.abort();
      seq.current++;                         // invalidate any response that lands after submit
      setValue(p); setTyped(p);
      setGhost(""); setSuggestions([]); setActive(-1); setOpen(false);
      onRun(p);
    }
  };

  const pick = (s: string) => { setValue(s); setTyped(s); submit(s); };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const atEnd = inputRef.current ? inputRef.current.selectionStart === value.length : true;
    if ((e.key === "Tab" || (e.key === "ArrowRight" && atEnd)) && ghost) {
      e.preventDefault(); acceptGhost(); return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); moveActive(1); return; }
    if (e.key === "ArrowUp") { e.preventDefault(); moveActive(-1); return; }
    if (e.key === "Enter") {
      // Enter runs the highlighted suggestion, else the typed text
      e.preventDefault();
      submit(active >= 0 ? suggestions[active] : value);
      return;
    }
    if (e.key === "Escape") {
      setActive(-1); setValue(typed); setSuggestions([]); setGhost(""); setOpen(false);
    }
  };

  const showDrop = open && suggestions.length > 0 && !loading;
  const showTab = ghost.length > 0 && active === -1 && !loading;

  // a suggestion split into the typed prefix (muted) and the completion (bold teal) — Space Mono
  const renderSug = (s: string) => {
    const t = typed.trim();
    if (t && s.toLowerCase().startsWith(t.toLowerCase())) {
      return (<span className="txt"><span className="pfx">{s.slice(0, t.length)}</span><b>{s.slice(t.length)}</b></span>);
    }
    return <span className="txt"><b>{s}</b></span>;
  };

  return (
    <div className="cc-pb">
      <div className="cc-pb-pill">
        <span className="cc-pb-spark"><Spark /></span>

        <div className="cc-pb-field">
          <div className="cc-pb-ghost" ref={ghostRef} aria-hidden>
            <span className="typed">{value}</span>
            {ghost && active === -1 ? <span className="g">{ghost}</span> : null}
          </div>
          <input
            ref={inputRef}
            className="cc-pb-input"
            value={value}
            placeholder="Ask the copilot to monitor, analyze, or report"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            onScroll={(e) => { if (ghostRef.current) ghostRef.current.scrollLeft = e.currentTarget.scrollLeft; }}
            onFocus={() => { if (suggestions.length) setOpen(true); }}
            onBlur={() => { blurT.current = window.setTimeout(() => setOpen(false), 140); }}
            disabled={loading}
          />
        </div>

        {showTab && <span className="cc-pb-tab">TAB</span>}

        <button className="cc-pb-run" onClick={() => submit()} disabled={loading} title="Run command" aria-label="Run command">
          <Return />
        </button>
      </div>

      {loading && <div className="cc-pb-progress"><i /></div>}

      {showDrop && (
        <div className="cc-pb-drop" onMouseDown={(e) => { e.preventDefault(); window.clearTimeout(blurT.current); }}>
          {suggestions.map((s, i) => (
            <div
              key={s}
              className={"cc-pb-row" + (i === active ? " active" : "")}
              onMouseEnter={() => { setActive(i); setValue(s); setGhost(""); }}
              onMouseLeave={() => { setActive(-1); setValue(typed); }}
              onClick={() => pick(s)}
            >
              <span className="ico"><Mag /></span>
              {renderSug(s)}
              <span className="ret">↵</span>
            </div>
          ))}
          <div className="cc-pb-foot">
            <div className="keys"><span>↑↓ navigate</span><span>↵ run</span><span>esc dismiss</span></div>
            {lat != null && <div className="lat">copilot · {lat} ms</div>}
          </div>
        </div>
      )}
    </div>
  );
}
