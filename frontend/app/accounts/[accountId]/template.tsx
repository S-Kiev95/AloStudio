import type { ReactNode } from "react";

export default function AccountTemplate({
  children,
}: {
  children: ReactNode;
}) {
  return <div className="page-enter">{children}</div>;
}
