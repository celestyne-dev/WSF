import { Component } from 'react'

// A single top-level boundary (wraps <App/> in main.jsx) so an unexpected
// render error anywhere in the tree shows a plain, on-brand fallback
// instead of a blank white screen — never a React/Vite stack trace to a
// real visitor. Deliberately minimal: this is a production safety net,
// not a per-route recovery system (a route-level error should be handled
// by that route's own loading/empty state instead).
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error, info) {
    // console.error (not console.log) is the one console call this
    // production-readiness pass deliberately keeps: a real render crash
    // belongs in the browser console for whoever is debugging it, and
    // there is no backend endpoint to report it to (no third-party
    // monitoring vendor is part of this app's scope — see DEPLOYMENT.md).
    console.error('Unhandled render error caught by ErrorBoundary:', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-ivory px-6 text-center">
        <p className="eyebrow">Something went wrong</p>
        <h1 className="mt-3 font-serif text-3xl font-semibold text-charcoal sm:text-4xl">
          We hit an unexpected error
        </h1>
        <p className="mt-4 max-w-md text-charcoal-600">
          Please try reloading the page. If the problem continues, come back in a few minutes.
        </p>
        <button type="button" onClick={() => window.location.assign('/')} className="btn-primary mt-8">
          Back to homepage
        </button>
      </div>
    )
  }
}
