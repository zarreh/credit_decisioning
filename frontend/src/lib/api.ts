import type { Detail, Draft, Evidence, Summary, VerifierReport } from "@/lib/types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

// `make run` starts the web app a few seconds before the API has loaded the model, so a
// read that finds nothing listening is retried briefly. Writes are never retried.
const READ_RETRIES = 6;
const RETRY_DELAY_MS = 1500;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isRead = (init?.method ?? "GET") === "GET";
  let res: Response | undefined;
  for (let attempt = 0; res === undefined; attempt++) {
    try {
      res = await fetch(`${API_BASE}${path}`, {
        ...init,
        headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
        cache: "no-store",
      });
    } catch {
      if (!isRead || attempt >= READ_RETRIES) {
        throw new ApiError(
          0,
          `Cannot reach the API at ${API_BASE}. Is it running? Start it with "make dev" (or "make run" for both), then reload.`,
        );
      }
      await sleep(RETRY_DELAY_MS);
    }
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  queue: () => request<Summary[]>("/applications"),
  application: (id: string) => request<Detail>(`/applications/${encodeURIComponent(id)}`),
  start: (id: string) => request<Detail>(`/applications/${encodeURIComponent(id)}/start`, { method: "POST" }),
  act: (id: string, body: Record<string, unknown>) =>
    request<Detail>(`/applications/${encodeURIComponent(id)}/actions`, { method: "POST", body: JSON.stringify(body) }),
  evidence: () => request<Evidence>("/evidence"),
  verifier: () => request<VerifierReport>("/evidence/verifier"),
  analystStatus: () => request<{ enabled: boolean; model: string | null }>("/analyst/status"),
  reports: () => request<Draft[]>("/analyst/reports"),
};

export type StreamEvent = { event: string; data: Record<string, unknown> };

/** POST and read a server-sent-event stream, calling onEvent for each event. */
export async function postStream(path: string, body: unknown, onEvent: (e: StreamEvent) => void): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_BASE}.`);
  }
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, String(detail));
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let split: number;
    while ((split = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data.push(line.slice(5).trim());
      }
      if (data.length) onEvent({ event, data: JSON.parse(data.join("\n")) });
    }
  }
}

/** Deterministic UTC timestamp (no locale formatting, so no hydration mismatch). */
export const fmtTime = (iso: string) => iso.slice(0, 16).replace("T", " ") + " UTC";
export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;
export const num = (x: number, digits = 2) => x.toFixed(digits);
