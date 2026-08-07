

import type { Bucket, ResponseType } from "@/lib/filters";

export const HV_BUILTIN_KEYWORDS = [
  "USER_NOT_LOGIN",
  "用户未登录",
  "请重新登录",
  "请先登录",
  "登录失效",
  "登录已过期",
  "登录信息已过期",
  "会话过期",
  "会话超时",
  "SESSION_EXPIRED",
  "LOGIN_FAILURE",
  "未认证",
  "not logged in",
  "not login!",
  "not authenticated",
  "UNAUTHENTICATED",
  "cannot get user info",
  "NO_PERMISSION",
  "用户信息失效",
  "token不存在",
  "token失效",
  "token已过期",
  "sessionId无效",
  "用户请求未携带token",
];

export const HV_MAX_CUSTOM = 30;

export type HighValueState = {
  on: boolean;
  builtinEnabled: string[];
  customKeywords: string[];
  preBuckets: Bucket[] | null;
  preRespCts: ResponseType[] | null;
};

export function defaultHighValue(): HighValueState {
  return {
    on: false,
    builtinEnabled: [...HV_BUILTIN_KEYWORDS],
    customKeywords: [],
    preBuckets: null,
    preRespCts: null,
  };
}

export function sanitizeHighValue(value: unknown): HighValueState {
  const base = defaultHighValue();
  if (!value || typeof value !== "object") return base;
  const raw = value as Partial<HighValueState>;
  const builtins = Array.isArray(raw.builtinEnabled)
    ? raw.builtinEnabled.filter((item) => HV_BUILTIN_KEYWORDS.includes(item))
    : base.builtinEnabled;
  const custom = Array.isArray(raw.customKeywords)
    ? Array.from(new Set(raw.customKeywords.filter((item) => typeof item === "string").map(normalizeCustomKeyword).filter(Boolean))).slice(0, HV_MAX_CUSTOM)
    : [];
  return {
    on: !!raw.on,
    builtinEnabled: builtins,
    customKeywords: custom,
    preBuckets: Array.isArray(raw.preBuckets) ? (raw.preBuckets as Bucket[]) : null,
    preRespCts: Array.isArray(raw.preRespCts) ? (raw.preRespCts as ResponseType[]) : null,
  };
}

export function normalizeCustomKeyword(value: string) {
  return value.trim().replace(/\s*:\s*/g, ":").replace(/\s*,\s*/g, ",");
}
