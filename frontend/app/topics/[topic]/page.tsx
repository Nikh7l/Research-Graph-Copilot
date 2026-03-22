import { AppShell } from "../../../components/app-shell";
import { EntityCard } from "../../../components/entity-card";

export default async function TopicPage(props: { params: Promise<{ topic: string }> }) {
  const { topic } = await props.params;
  const label = decodeURIComponent(topic).replace(/-/g, " ");

  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Topic</p>
        <h1>{label}</h1>
        <p>Topic summary, methods, and evidence-backed changes will render here after the backend is connected.</p>
      </section>
      <section className="grid">
        <EntityCard title="Methods" description="Canonical method clusters linked to the topic." />
        <EntityCard title="Claims" description="Supporting and conflicting claims from the paper corpus." />
        <EntityCard title="Changes" description="Date-bounded summary of what changed across the corpus." />
      </section>
    </AppShell>
  );
}

