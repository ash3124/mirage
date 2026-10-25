export class ApiError extends Error {
  readonly code: string;
  readonly status: number | undefined;

  constructor(code: string, message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

interface ErrorPayload {
  error?: {
    code?: unknown;
    message?: unknown;
  };
}

function isErrorPayload(value: unknown): value is ErrorPayload {
  return typeof value === 'object' && value !== null && 'error' in value;
}

function headersFor(url: string, headers?: HeadersInit): Headers {
  const result = new Headers(headers);
  const hostname = new URL(url).hostname;
  if (hostname.includes('ngrok')) {
    result.set('ngrok-skip-browser-warning', '1');
  }
  return result;
}

async function throwApiError(response: Response): Promise<never> {
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(
      'INTERNAL',
      'The server returned an unreadable error response.',
      response.status,
    );
  }

  if (isErrorPayload(payload)) {
    const code = payload.error?.code;
    const message = payload.error?.message;
    if (typeof code === 'string' && typeof message === 'string') {
      throw new ApiError(code, message, response.status);
    }
  }

  throw new ApiError(
    'INTERNAL',
    'The server returned an invalid error response.',
    response.status,
  );
}

export function createHttpClient(configuredBase?: string) {
  const configured = configuredBase || import.meta.env.VITE_API_BASE || window.location.origin;
  const withoutApiPrefix = configured.replace(/\/+$/, '').replace(/\/api\/v1$/, '');
  const origin = new URL(withoutApiPrefix, window.location.origin).origin;
  const apiPrefix = `${origin}/api/v1`;

  async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
    const url = `${apiPrefix}${path}`;
    const response = await fetch(url, {
      ...init,
      headers: headersFor(url, init.headers),
    });
    if (!response.ok) {
      await throwApiError(response);
    }
    return (await response.json()) as T;
  }

  async function requestBlob(path: string, init: RequestInit = {}): Promise<Blob> {
    const url = `${apiPrefix}${path}`;
    const response = await fetch(url, {
      ...init,
      headers: headersFor(url, init.headers),
    });
    if (!response.ok) {
      await throwApiError(response);
    }
    return response.blob();
  }

  return {
    requestJson,
    requestBlob,
    absoluteUrl(path: string): string {
      return new URL(path, `${origin}/`).toString();
    },
  };
}
