/** API 클라이언트.
 *
 * 서버 오류를 그대로 던지지 않고 `ApiError` 로 감싼다. 화면에는 사람이 읽을 수
 * 있는 문장만 보여주고, traceback 성격의 원문은 `technical` 에 담아 두었다가
 * "기술 정보 보기" 를 눌렀을 때만 펼친다.
 */

export class ApiError extends Error {
  status: number;
  technical?: string;

  constructor(message: string, status: number, technical?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.technical = technical;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch (cause) {
    throw new ApiError(
      "백엔드에 연결하지 못했습니다. 서버가 실행 중인지 확인해 주세요.",
      0,
      String(cause),
    );
  }

  if (response.status === 204) return undefined as T;

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    const payload = body as { detail?: unknown; technical?: string } | null;
    let detail = "요청을 처리하지 못했습니다.";
    if (typeof payload?.detail === "string") detail = payload.detail;
    else if (Array.isArray(payload?.detail)) {
      const first = payload.detail[0] as { msg?: string } | undefined;
      if (first?.msg) detail = first.msg;
    }
    throw new ApiError(detail, response.status, payload?.technical ?? text);
  }

  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export function buildQuery(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params as Record<string, unknown>)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      value.forEach((item) => search.append(key, String(item)));
    } else if (typeof value === "boolean") {
      if (value) search.set(key, "true");
    } else {
      search.set(key, String(value));
    }
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}
