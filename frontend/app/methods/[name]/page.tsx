import { AppShell } from "../../../components/app-shell";

export default async function MethodPage(props: { params: Promise<{ name: string }> }) {
  const { name } = await props.params;
  return (
    <AppShell>
      <section className="hero">
        <p className="eyebrow">Method</p>
        <h1>{decodeURIComponent(name)}</h1>
        <p>Method evidence, supporting claims, and linked papers will appear here.</p>
      </section>
    </AppShell>
  );
}

