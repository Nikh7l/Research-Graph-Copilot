import type { ReactNode } from "react";

export function AppShell(props: { children: ReactNode }) {
  return <main className="shell">{props.children}</main>;
}

