export function EntityCard(props: { title: string; description: string }) {
  return (
    <section className="card">
      <p className="eyebrow">Entity</p>
      <h3>{props.title}</h3>
      <p className="muted">{props.description}</p>
    </section>
  );
}

