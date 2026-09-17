"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="loading-page">
      <p className="eyebrow">OUTBREAK ATLAS</p>
      <h1>The view could not be loaded.</h1>
      <p>Please retry to reconnect to the official reports.</p>
      <button className="button primary" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
