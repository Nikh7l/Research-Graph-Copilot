import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "AI Research Intelligence Copilot",
  description: "GraphRAG + Neo4j + MCP research intelligence app."
};

export default function RootLayout(props: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{props.children}</body>
    </html>
  );
}

