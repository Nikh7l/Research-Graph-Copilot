import { AppShell } from "../../../components/app-shell";

export default async function PaperPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Paper</p>
        <h1>{id}</h1>
        <p>Paper metadata, abstract, extracted methods, and claims will appear here.</p>
      </section>
    </AppShell>
  );
}

