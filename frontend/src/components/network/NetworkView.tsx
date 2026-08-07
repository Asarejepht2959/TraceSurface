
import { Clipboard, FileText, Link2, Terminal, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { BodyBlock } from "@/components/shared/BodyBlock";
import { DetailPanel } from "@/components/shared/DetailPanel";
import { DetailTabs } from "@/components/shared/DetailTabs";
import { EmptyState } from "@/components/shared/EmptyState";
import { TableSkeleton } from "@/components/shared/TableSkeleton";
import { HeaderGrid } from "@/components/shared/HeaderGrid";
import { KvGrid } from "@/components/shared/KvGrid";
import { Pager } from "@/components/shared/Pager";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { bucketFromStatus, fmtBytes, headerValue, hostFromUrl, shortContentType } from "@/lib/format";
import { parseSearchPrefix, type FilterState } from "@/lib/filters";
import { requestToCurl, requestToRawHttp } from "@/lib/request";
import type { CdpDetail, CdpListItem, PageResult } from "@/types/api";
import { cn } from "@/lib/utils";

type NetworkViewProps = {
  filters: FilterState;
  toast: (message: string) => void;
  onResultLabel: (label: string) => void;
};

type DetailTab = "response" | "request";

export function NetworkView({ filters, toast, onResultLabel }: NetworkViewProps) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState<PageResult<CdpListItem>>({ total: 0, items: [] });
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selected, setSelected] = useState<CdpDetail | null>(null);
  const [tab, setTab] = useState<DetailTab>("response");

  const params = useMemo(() => {
    const parsed = parseSearchPrefix(filters.search);
    const query: Record<string, string | number> = {
      limit: pageSize,
      offset: (page - 1) * pageSize,
    };
    if (filters.target) query.target = filters.target;
    if (filters.methods.length < 5) query.methods = filters.methods.join(",");
    if (parsed.search) query.q = parsed.search;
    return query;
  }, [filters.search, filters.target, filters.methods, page, pageSize]);

  useEffect(() => {
    setPage(1);
    setSelected(null);
    setSelectedId(null);
  }, [filters.search, filters.target, filters.methods]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .cdpRequests(params)
      .then((next) => {
        if (cancelled) return;
        setData(next);
        onResultLabel(`${next.total} 条`);
      })
      .catch(() => {
        if (!cancelled) onResultLabel("-");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [params, onResultLabel]);

  const select = async (id: number) => {
    setSelectedId(id);
    setSelected(null);
    try {
      setSelected(await api.cdpRequest(id));
    } catch {
      toast("加载详情失败");
    }
  };

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden">
      <section className="flex min-w-0 flex-1 flex-col bg-surface-content">
        <div className="min-h-0 flex-1 overflow-auto">
          <table className={cn("data-table", selectedId ? "min-w-[760px]" : "min-w-[900px]")}>
            <colgroup>
              <col className={selectedId ? "w-[74px]" : "w-[86px]"} />
              <col className={selectedId ? "w-[74px]" : "w-[82px]"} />
              <col />
              <col className={selectedId ? "w-[78px]" : "w-[86px]"} />
              <col className={selectedId ? "w-[116px]" : "w-[126px]"} />
              <col className={selectedId ? "w-[170px]" : "w-[190px]"} />
            </colgroup>
            <thead>
              <tr>
                <th>Status</th>
                <th>Method</th>
                <th>Path</th>
                <th className="text-right">Size</th>
                <th>Type</th>
                <th>Origin</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <TableSkeleton columns={6} />
              ) : data.items.length ? (
                data.items.map((item) => <CdpRow key={item.id} item={item} selected={item.id === selectedId} onClick={() => select(item.id)} />)
              ) : (
                <tr><td colSpan={6}><EmptyState title="无 Network 请求" /></td></tr>
              )}
            </tbody>
          </table>
        </div>
        <Pager total={data.total} page={page} pageSize={pageSize} onChange={({ page: p, pageSize: ps }) => { setPage(p); setPageSize(ps); }} />
      </section>
      {selectedId ? <CdpDetailPanel id={selectedId} detail={selected} tab={tab} onTabChange={setTab} onClose={() => { setSelectedId(null); setSelected(null); }} toast={toast} /> : null}
    </div>
  );
}

// 单行 CDP 网络请求
function CdpRow({ item, selected, onClick }: { item: CdpListItem; selected: boolean; onClick: () => void }) {
  const status = item.response_status;
  const bucket = bucketFromStatus(status);
  const host = hostFromUrl(item.request_url);
  return (
    <tr className={cn(selected && "selected")} onClick={onClick}>
      <td><span className={`status-cell status-${bucket}`}><span className="status-bar" />{status == null ? "-" : status}</span></td>
      <td><span className={`method-badge method-${item.method}`}>{item.method}</span></td>
      <td className="overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[12.5px]" title={item.request_url}>{item.request_path || item.request_url}</td>
      <td className="text-right font-mono text-[12px] text-text-2">{fmtBytes(item.response_size)}</td>
      <td title={shortContentType(item.resp_ct) || "-"}><span className="tag">{shortContentType(item.resp_ct) || "-"}</span></td>
      <td className="overflow-hidden text-ellipsis whitespace-nowrap font-mono text-[11.5px] text-text-3" title={host}>{host}</td>
    </tr>
  );
}

// CDP 请求详情面板：响应/请求 Tab，复制 cURL/HTTP 快捷按钮
function CdpDetailPanel({
  id,
  detail,
  tab,
  onTabChange,
  onClose,
  toast,
}: {
  id: number;
  detail: CdpDetail | null;
  tab: DetailTab;
  onTabChange: (tab: DetailTab) => void;
  onClose: () => void;
  toast: (message: string) => void;
}) {
  const bodySectionRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!detail) return;
    window.requestAnimationFrame(() => {
      bodySectionRef.current?.scrollIntoView({ block: "start" });
    });
  }, [detail?.id, tab]);

  if (!detail) {
    return (
      <DetailPanel>
        <div className="flex h-full flex-col items-center justify-center gap-2 font-mono text-text-3">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-line-2 border-t-brand" />
          <span className="text-[11px] uppercase text-text-4">REQUEST #{id}</span>
        </div>
      </DetailPanel>
    );
  }
  const status = detail.response_status;
  const bucket = bucketFromStatus(status);
  const respHeaders = detail.response_headers || {};
  const reqHeaders = detail.request_headers || {};
  const respCt = headerValue(respHeaders, "content-type");
  const respCtShort = shortContentType(respCt);
  const req = { method: detail.method, url: detail.request_url, headers: reqHeaders, body: detail.post_data || "" };
  const copy = async (value: string) => {
    await navigator.clipboard?.writeText(value);
    toast("已复制");
  };
  const host = hostFromUrl(detail.request_url);

  return (
    <DetailPanel>
      <div className="detail-header">
        <button type="button" className="absolute right-4 top-4 inline-flex h-7 w-7 items-center justify-center rounded-full border border-line-2 text-text-3 transition-colors hover:bg-ink-2 hover:text-text" onClick={onClose} title="关闭详情">
          <X className="h-4 w-4" />
        </button>
        <div className="mb-3 flex items-center gap-2">
          <span className={`method-badge method-${detail.method}`}>{detail.method}</span>
          <span className={`status-cell status-${bucket}`}><span className="status-bar" />{status == null ? "- no response" : status}</span>
        </div>
        <button className="block break-all text-left font-mono text-[13px] leading-5 text-text hover:text-brand" onClick={() => copy(detail.request_url)}>
          {detail.request_url}
        </button>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10.5px] text-text-3">
          <span className="min-w-0 break-all">ORIGIN <b className="text-text">{host || "-"}</b></span>
          <span className="min-w-0 break-all">SIZE <b className="text-text">{fmtBytes(detail.response_size)}</b></span>
          <span className="min-w-0 break-all">TYPE <b className="text-text">{respCtShort || "-"}</b></span>
        </div>
      </div>
      <DetailTabs value={tab} items={[{ value: "response", label: "Response" }, { value: "request", label: "Request" }]} onChange={onTabChange} />
      <div className="detail-body">
        {tab === "request" ? (
          <>
            <section className="section">
              <div className="section-title">Target</div>
              <KvGrid items={[{ label: "Method", value: detail.method }, { label: "URL", value: detail.request_url }, { label: "Query", value: detail.query_string || "", hidden: !detail.query_string }, { label: "Type", value: detail.content_type || "", hidden: !detail.content_type }]} />
            </section>
            <section className="section"><div className="section-title">Request Headers</div><HeaderGrid headers={reqHeaders} /></section>
            <section ref={bodySectionRef} className="section"><div className="section-title">Request Body</div><BodyBlock value={detail.post_data} empty="无请求 body" /></section>
          </>
        ) : (
          <>
            <section className="section">
              <div className="section-title">Status</div>
              <KvGrid items={[{ label: "Status", value: <span className={`status-${bucket}`}>{status == null ? "- no response" : status}</span> }, { label: "Length", value: fmtBytes(detail.response_size) }, { label: "Type", value: respCtShort || "-", hidden: !respCtShort }]} />
            </section>
            <CdpReplaySection detail={detail} />
            <section className="section"><div className="section-title">Response Headers</div><HeaderGrid headers={respHeaders} /></section>
            <section ref={bodySectionRef} className="section">
              <div className="section-title">Response Body</div>
              {detail.response_body_truncated ? <div className="trunc-banner">正文已截断 {fmtBytes(1024 * 1024)} / 原 {fmtBytes(detail.response_body_full_size)}</div> : null}
              {detail.response_body ? <BodyBlock value={detail.response_body} /> : detail.response_size ? <div className="body-empty text-brand">二进制响应 · {fmtBytes(detail.response_size)}</div> : <div className="body-empty">{status == null ? "无响应（请求未完成）" : "无响应正文"}</div>}
            </section>
          </>
        )}
      </div>
      <div className="detail-actions">
        <Button variant="default" onClick={() => copy(requestToCurl(req))}><Terminal className="h-3.5 w-3.5" />Copy as cURL</Button>
        <Button variant="subtle" onClick={() => copy(requestToRawHttp(req))}><FileText className="h-3.5 w-3.5" />Copy as HTTP</Button>
        <Button variant="subtle" onClick={() => copy(detail.request_url)}><Link2 className="h-3.5 w-3.5" />Copy URL</Button>
        <Button variant="subtle" onClick={() => copy(detail.response_body || "")}><Clipboard className="h-3.5 w-3.5" />Copy response</Button>
      </div>
    </DetailPanel>
  );
}

// 无认证复发区：这条「带认证」的真实请求被去掉认证头后复发的结果，2xx 即提示无认证可访问
function CdpReplaySection({ detail }: { detail: CdpDetail }) {
  const reps = detail.verifications || [];
  return (
    <section className="section">
      <div className="section-title">无认证复发</div>
      {reps.length ? (
        <div className="flex flex-col gap-1.5">
          {reps.map((v) => {
            const vb = bucketFromStatus(v.status, v.error);
            const reachable = typeof v.status === "number" && v.status >= 200 && v.status < 300;
            return (
              <a key={v.id} href={`/api/replays/${v.id}`} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-[11.5px] hover:underline">
                <span className={`status-cell status-${vb}`}><span className="status-bar" />{v.error || v.status == null ? "ERR" : v.status}</span>
                <span className="font-mono text-text-2">{v.sent_method}</span>
                {reachable ? <span className="font-medium text-red">⚠ 无认证可访问</span> : <span className="text-text-3">已拦截 / 不可达</span>}
              </a>
            );
          })}
        </div>
      ) : (
        <div className="body-empty">尚无复发结果（仅发包模式下产生）</div>
      )}
    </section>
  );
}
