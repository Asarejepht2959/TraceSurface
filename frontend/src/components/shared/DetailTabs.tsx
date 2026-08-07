
import { cn } from "@/lib/utils";

type DetailTabsProps<T extends string> = {
  value: T;
  items: Array<{ value: T; label: string }>;
  onChange: (value: T) => void;
};

export function DetailTabs<T extends string>({ value, items, onChange }: DetailTabsProps<T>) {
  return (
    <div className="flex shrink-0 border-b border-line bg-surface-chrome px-4">
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          className={cn(
            "relative mb-[-1px] px-4 py-3 text-[11.5px] font-medium text-text-3 transition-colors hover:text-text-2",
            item.value === value && "text-text after:absolute after:bottom-0 after:left-3.5 after:right-3.5 after:h-0.5 after:rounded-full after:bg-brand",
          )}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
