export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T>(path: string, opts: { token?: string | null; method?: string; body?: unknown } = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
    method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
    headers: {
      ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(opts.token ? { Authorization: `Bearer ${opts.token}` } : {}),
    },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
    });
  } catch {
    // El navegador no da detalles: o la API no responde, o la bloquea CORS (origen no permitido)
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    throw new ApiError(0, `No se puede conectar con la API (${API_URL}). Si la web está publicada, en Render → Environment ` +
      `CDD_CORS_ORIGINS debe incluir ${origin || "la dirección de esta web"}. Si la API estaba dormida, espera 1 minuto y recarga.`);
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* */ }
    throw new ApiError(res.status, msg);
  }
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export function formatUsd(v: string | number | null | undefined): string {
  const n = Number(v ?? 0);
  return n.toLocaleString("es", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 4 });
}

export function formatDate(s: string | null | undefined): string {
  return s ? new Date(s).toLocaleString("es", { dateStyle: "medium", timeStyle: "short" }) : "—";
}
