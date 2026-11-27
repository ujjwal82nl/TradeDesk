import axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';

const getBaseUrl = (): string => {
  let base = process.env.REACT_APP_API_URL || '';
  if (!base && typeof window !== 'undefined') {
    if (window.location.pathname.startsWith('/opt')) {
      base = '/opt';
    } else if (window.location.port === '3000') {
      base = 'http://localhost:8000';
    }
  }
  if (!base) {
    base = 'http://localhost:8000';
  }

  // Normalize: remove trailing slash, prevent duplicate /api
  base = base.replace(/\/+$/, '');
  if (base.endsWith('/api/v1')) {
    return base;
  }
  if (base.endsWith('/api')) {
    return `${base}/v1`;
  }
  return `${base}/api/v1`;
};

export const api = axios.create({
  baseURL: getBaseUrl(),
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

/** Alias for backwards compatibility */
export const apiClient = api;

// ─── Request interceptor – attach access token ─────────────────────────────
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('accessToken');
    if (token && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error),
);

// ─── Response interceptor – handle 401 with silent token refresh ───────────
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}
function onRefreshed(token: string) {
  refreshSubscribers.forEach(cb => cb(token));
  refreshSubscribers = [];
}

api.interceptors.response.use(
  response => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(buildReadableError(error));
    }
    originalRequest._retry = true;

    if (isRefreshing) {
      return new Promise(resolve => {
        subscribeTokenRefresh(token => {
          if (originalRequest.headers) {
            (originalRequest.headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
          }
          resolve(api(originalRequest));
        });
      });
    }

    const refreshToken = localStorage.getItem('refreshToken');
    if (!refreshToken) { clearAuthAndRedirect(); return Promise.reject(buildReadableError(error)); }

    isRefreshing = true;
    try {
      const { data } = await axios.post<{ access_token: string; refresh_token: string }>(
        `${getBaseUrl()}/auth/refresh`,
        { refresh_token: refreshToken },
      );
      localStorage.setItem('accessToken',  data.access_token);
      localStorage.setItem('refreshToken', data.refresh_token);
      onRefreshed(data.access_token);
      if (originalRequest.headers) {
        (originalRequest.headers as Record<string, string>)['Authorization'] = `Bearer ${data.access_token}`;
      }
      return api(originalRequest);
    } catch {
      clearAuthAndRedirect();
      return Promise.reject(buildReadableError(error));
    } finally {
      isRefreshing = false;
    }
  },
);

function clearAuthAndRedirect() {
  localStorage.removeItem('accessToken');
  localStorage.removeItem('refreshToken');
  localStorage.removeItem('user');
  const isOpt = typeof window !== 'undefined' && window.location.pathname.startsWith('/opt');
  window.location.href = isOpt ? '/opt/login' : '/login';
}

function buildReadableError(error: AxiosError | unknown): Error {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as Record<string, unknown> | undefined;
    const detail = typeof data?.detail === 'string' ? data.detail : typeof data?.message === 'string' ? data.message : error.message;
    const status = error.response?.status;
    return new Error(status ? `[${status}] ${detail}` : detail);
  }
  if (error instanceof Error) return error;
  return new Error('An unexpected error occurred');
}
