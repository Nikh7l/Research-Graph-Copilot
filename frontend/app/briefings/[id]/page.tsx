import { AppShell } from "../../../components/app-shell";

export default async function BriefingPage(props: { params: Promise<{ id: string }> }) {
  const { id } = await props.params;
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Briefing</p>
        <h1>{id}</h1>
        <p>Saved briefings will display their summary, cited papers, and date bounds here.</p>
      </section>
    </AppShell>
  );
}
