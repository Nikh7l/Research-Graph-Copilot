import Link from "next/link";

import { AppShell } from "../components/app-shell";
import { EvidencePanel } from "../components/evidence-panel";
import { EntityCard } from "../components/entity-card";
import { QueryForm } from "../components/query-form";

const prompts = [
  "What changed in agent tool-call reliability between 2025-01-01 and 2026-03-22?",
  "Which methods for reducing tool-call errors appear most often in recent papers?",
  "Generate a briefing on structured outputs and reliability techniques."
];

export default function HomePage() {
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">AI Research Intelligence Copilot</p>
        <h1>Trace the shape of agent reliability research.</h1>
        <p>
          A local-first research graph that ingests a bounded paper corpus, extracts methods and claims,
          stores them in Neo4j, and exposes evidence-backed answers through an API, a web app, and MCP tools.
        </p>
      </section>

      <section className="grid" style={{ marginBottom: 18 }}>
        <QueryForm />
        <EvidencePanel />
      </section>

      <section className="grid" style={{ marginBottom: 18 }}>
        <EntityCard
          title="Topic Overview"
          description="View themes, recent changes, and top methods for the configured research slice."
        />
        <EntityCard
          title="Method Detail"
          description="Inspect supporting claims, linked papers, and compare competing reliability techniques."
        />
        <EntityCard
          title="Saved Briefings"
          description="Export concise, date-bounded research summaries with citations."
        />
      </section>

      <section className="card" style={{ maxWidth: 960, margin: "0 auto" }}>
        <p className="eyebrow">Starter Prompts</p>
        <ul className="prompt-list">
          {prompts.map((prompt) => (
            <li className="prompt-item" key={prompt}>
              {prompt}
            </li>
          ))}
        </ul>
        <p className="muted">
          Explore <Link href="/topics/agent-tool-call-reliability">topic view</Link> once data is loaded.
        </p>
      </section>
    </AppShell>
  );
}

