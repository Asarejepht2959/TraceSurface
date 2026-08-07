
import type { ReactNode } from "react";

type KvGridProps = {
  items: Array<{ label: string; value: ReactNode; hidden?: boolean }>;
};

export function KvGrid({ items }: KvGridProps) {
  return (
    <div className="kv-grid">
      {items
        .filter((item) => !item.hidden)
        .map((item) => (
          <div key={item.label} className="contents">
            <div className="k">{item.label}</div>
            <div className="v">{item.value}</div>
          </div>
        ))}
    </div>
  );
}
