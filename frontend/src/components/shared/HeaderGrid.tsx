
export function HeaderGrid({ headers }: { headers: Record<string, unknown> }) {
  const entries = Object.entries(headers);
  if (!entries.length) return <div className="font-mono text-[12px] italic text-text-4">无</div>;
  return (
    <div className="kv-grid">
      {entries.map(([key, value]) => (
        <div key={key} className="contents">
          <div className="k">{key}</div>
          <div className="v">{String(value)}</div>
        </div>
      ))}
    </div>
  );
}
