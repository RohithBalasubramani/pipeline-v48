import React from "react";

const CLEAN = { has: false, e: null as any };

// The ONE error-boundary class — the three hand-rolled boundaries (app root / per-card / per-piece) differed only in
// fallback JSX. Each call site keeps its exact fallback via the `fallback` render prop. Per-leaf-degradation contract
// untouched: boundaries stay exactly where they were.
export class ErrorBoundary extends React.Component<
  {
    children: React.ReactNode;
    /** Renders the fallback UI from the caught error text. */
    fallback: (err: string) => React.ReactNode;
    /** How to stringify the caught value (app root wants the stack; cards want the message). */
    errorText?: (e: any) => string;
    /** Optional side-channel (e.g. console.error at the app root). */
    onCatch?: (e: any, info: any) => void;
  },
  { has: boolean; e: any }
> {
  state = { ...CLEAN };
  static getDerivedStateFromError(e: any) {
    return { has: true, e };   // raw error in state; formatting happens in render() where props are reachable
  }
  componentDidCatch(e: any, info: any) {
    this.props.onCatch?.(e, info);
  }
  /** Recover hook (the app-root "Retry render" button). */
  reset = () => this.setState({ ...CLEAN });
  render() {
    if (this.state.has) {
      const fmt = this.props.errorText ?? ((x: any) => String(x?.message ?? x));
      return this.props.fallback(fmt(this.state.e));
    }
    return this.props.children;
  }
}
