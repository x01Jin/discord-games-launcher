import type { PywebviewApi } from "./types";

const READY_TIMEOUT_MS = 20_000;
const POLL_MS = 40;

async function awaitApi<K extends keyof PywebviewApi>(method: K): Promise<PywebviewApi> {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  for (;;) {
    const api = typeof window === "undefined" ? undefined : window.pywebview?.api;
    if (api && typeof api[method] === "function") return api;
    if (Date.now() > deadline) {
      throw new Error(
        "Backend unavailable: window.pywebview.api." +
          String(method) +
          " never appeared. Run the app through the Discord Games Launcher " +
          "desktop shell (or set DCGL_FRONTEND_URL for development).",
      );
    }
    await new Promise((resolve) => window.setTimeout(resolve, POLL_MS));
  }
}

export const bridge: PywebviewApi = new Proxy({} as PywebviewApi, {
  get(_target, property: keyof PywebviewApi) {
    return async (...args: unknown[]) => {
      const api = await awaitApi(property);
      const call = api[property] as (...rest: unknown[]) => Promise<unknown>;
      return call.apply(api, args);
    };
  },
});
