import type { PywebviewApi } from "./types";

function realApi(): PywebviewApi {
  if (typeof window !== "undefined" && window.pywebview?.api) {
    return window.pywebview.api;
  }
  throw new Error(
    "Backend unavailable: window.pywebview.api is undefined. " +
      "Run the app through the Discord Games Launcher desktop shell " +
      "(or set DCGL_FRONTEND_URL for development).",
  );
}

/**
 * Typed accessor for the Python bridge exposed as `window.pywebview.api`.
 * There is intentionally no mock fallback: outside the desktop shell every
 * call rejects and the pages render their error/empty states.
 */
export const bridge: PywebviewApi = new Proxy({} as PywebviewApi, {
  get(_target, prop: keyof PywebviewApi) {
    return (...args: unknown[]) =>
      (realApi()[prop] as (...a: unknown[]) => Promise<unknown>)(...args);
  },
});
