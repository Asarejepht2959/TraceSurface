
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { Stats } from "@/types/api";
import type { MainTab } from "@/types/state";

export const MAIN_TABS: Array<{ value: MainTab; label: string }> = [
  { value: "surface", label: "API Surface" },
  { value: "replays", label: "Verification" },
  { value: "cdp", label: "Network" },
  { value: "secrets", label: "Secrets" },
];

type TopBarProps = {
  stats: Stats | null;
  search: string;
  shortcutLabel: string;
  activeTab: MainTab;
  onTabChange: (tab: MainTab) => void;
  onSearch: (value: string) => void;
};

export function TopBar({ stats, search, shortcutLabel, activeTab, onTabChange, onSearch }: TopBarProps) {
  return (
    <header className="topbar">
      <div className="flex shrink-0 items-center gap-3">
        <div className="tracesurface-dot" aria-hidden="true" />
        <div className="leading-none">
          <div className="font-display text-[21px] font-bold tracking-[-0.01em] text-text">TraceSurface</div>
          <div className="mt-1 font-mono text-[8.5px] uppercase tracking-[0.34em] text-text-4">Inspector</div>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="主视图">
        {MAIN_TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            className={cn("nav-tab", activeTab === tab.value && "active")}
            aria-current={activeTab === tab.value ? "page" : undefined}
            onClick={() => onTabChange(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="flex min-w-0 flex-1 items-center justify-end gap-5">
        <div className="relative flex w-full min-w-[200px] max-w-md items-center">
          <Search className="pointer-events-none absolute left-3 h-4 w-4 shrink-0 text-text-4" />
          <Input
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="搜索 · url:/api/login body:password dom:example.com"
            title="无前缀=URL+响应+域名；前缀 url:/body:/dom: 限定单字段"
            data-tracesurface-search
            className="h-9 w-full min-w-0 pl-9 pr-20 font-mono text-[12px]"
          />
          <kbd className="pointer-events-none absolute right-2.5 rounded border border-line-2 bg-ink-2 px-1.5 py-0.5 font-mono text-[10px] text-text-3">{shortcutLabel}</kbd>
        </div>
        <TopStats stats={stats} />
      </div>
    </header>
  );
}

function TopStats({ stats }: { stats: Stats | null }) {
  const s = stats || { total: 0, target_count: 0, t_l1: 0, t_l2: 0, t_l3: 0, t_l4: 0 };
  return (
    <div className="hidden shrink-0 items-center gap-4 font-mono text-[11px] text-text-3 xl:flex">
      <StatNumber value={s.target_count} label="targets" />
      <StatNumber value={s.total} label="requests" />
      <div className="h-6 w-px bg-line-2" />
      <Popover>
        <PopoverTrigger asChild>
          <Button variant="subtle" size="sm" className="h-7 gap-1.5 px-2.5 text-[11px]">
            Tier
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-56 p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <span className="font-mono text-[10.5px] font-semibold uppercase tracking-wide text-text-2">Tier 分布</span>
            <TooltipProvider delayDuration={150}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-line-2 bg-ink-2 text-[10px] font-bold text-text-3 hover:bg-ink-3"
                  >
                    ?
                  </button>
                </TooltipTrigger>
                <TooltipContent className="w-72 leading-5">
                  <b className="text-text">Tier 表示 URL 推导把握度</b>
                  <br />
                  L1 最高，L4 最低（L4 为纯 origin 兜底）；它不代表响应可信度，是否存在仍看 status code。
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          <div className="grid grid-cols-2 gap-2 font-mono text-[12px]">
            <TierRow color="text-green" value={s.t_l1} label="L1" />
            <TierRow color="text-yellow" value={s.t_l2} label="L2" />
            <TierRow color="text-brand" value={s.t_l3} label="L3" />
            <TierRow color="text-text-4" value={s.t_l4} label="L4" />
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}

function StatNumber({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="font-display text-[18px] font-semibold tabular-nums text-text">{value}</span>
      <span className="text-[9.5px] uppercase tracking-wide text-text-4">{label}</span>
    </div>
  );
}

function TierRow({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 rounded border border-line bg-[var(--ink-0)] px-2.5 py-1.5">
      <span className="text-[10px] uppercase text-text-4">{label}</span>
      <span className={`font-display text-[15px] font-semibold tabular-nums ${color}`}>{value}</span>
    </div>
  );
}
