import { Component } from "react";

// Shows the error instead of a blank page if any component throws while rendering.
export default class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="app">
        <div className="card">
          <b>Something went wrong.</b>
          <div className="error">{String(this.state.error.message || this.state.error)}</div>
          <button onClick={() => window.location.reload()}>Reload</button>
        </div>
      </div>
    );
  }
}
