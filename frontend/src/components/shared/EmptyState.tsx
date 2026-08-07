
import { Inbox } from "lucide-react";

type EmptyStateProps = {
  title: string;
  hint?: string;
};

export function EmptyState({ title, hint }: EmptyStateProps) {
  return (
    <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2.5 p-10 text-center">
      <Inbox className="h-8 w-8 text-text-4" strokeWidth={1.5} />
      <div className="text-[13px] font-medium text-text-2">{title}</div>
      {hint ? <div className="max-w-sm font-mono text-[11px] leading-5 text-text-4">{hint}</div> : null}
    </div>
  );
}
