"use client";

import { useState } from "react";

export function QueryForm() {
  const [question, setQuestion] = useState(
    "What changed in agent tool-call reliability between 2025-01-01 and 2026-03-22?"
  );

  return (
    <section className="card">
      <p className="eyebrow">Ask</p>
      <textarea
        aria-label="Question"
        rows={4}
        style={{ width: "100%", padding: 12, borderRadius: 14, border: "1px solid var(--border)" }}
        value={question}
        onChange={(event) => setQuestion(event.target.value)}
      />
      <p className="muted">
        Wire this component to <code>POST /api/query</code> after backend dependencies are installed.
      </p>
    </section>
  );
}

