# Frontend

React 19, TypeScript, Vite and Tailwind 4. The built output goes to
`../frontend-dist`, which pywebview serves as `index.html`.

## Commands

```cmd
npm install
npm run dev     # Vite dev server against a browser, no pywebview
npm run build   # writes ../frontend-dist, restart the app to pick it up
npx tsc -b
npx oxlint src
```

The app only loads `frontend-dist`, so a source edit without `npm run build`
shows the old UI. Python and Vite do not share a dev server, so live reload is
only available in the browser.

## Layout

- `src/app` renders the shell and picks the page.
- `src/modules/*` holds a page per area: quests, catalogue, library, settings.
- `src/shared` holds the API client, components, hooks, store and formatters.

The bridge in `shared/api-client` waits for `window.pywebview.api` to expose the
method it needs, because pywebview injects an empty object first. Every call
returns `{ ok, ... }`; failures arrive as `error` strings rather than thrown
errors.
