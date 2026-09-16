# UI Documentation

## Overview

The Discord Games Launcher frontend is a React single-page application
rendered inside a pywebview native window. All backend access goes through
the typed `window.pywebview.api` bridge (`launcher/bridge.py`); the
contract is documented in [Bridge](./bridge.md).

**Stack:** React + Vite + Tailwind CSS
**Theme:** Dark mode with periwinkle accent
**State:** React Query (server state) + Zustand (UI state)

## File Structure

```structure
frontend/src/
├── App.tsx                        # Shell: fixed chrome + scroll views
├── main.tsx                       # React Query + store providers
├── index.css                      # Theme tokens, card/scrollbar styling
├── modules/
│   ├── catalogue/                 # Browse + search + add
│   │   ├── components/            # CataloguePage, GameCard
│   │   ├── hooks/                 # useCatalogue (queries + add mutations)
│   │   └── services/              # catalogue-service
│   └── library/                   # Library management + repair
│       ├── components/            # LibraryPage, LibraryCard
│       ├── hooks/                 # useLibrary (queries + mutations)
│       └── services/              # library-service
└── shared/
    ├── api-client/                # bridge proxy + TypeScript types
    ├── components/                # Header, Tabs, SearchBar, Footer,
    │                              # StatsModal, Toasts, ContextMenu
    ├── hooks/                     # useDcglEvents, useDebouncedValue
    └── store/                     # ui-store (Zustand)
```

## Theme

Tokens in `index.css` (`@theme`):

```css
--color-ink: #14151c; /* App background */
--color-card: #20222e; /* Cards, toolbar buttons */
--color-peri: #8f93f5; /* Primary accent */
--color-peri-strong: #a5a8ff; /* Accent hover */
--color-muted: #9aa0b4; /* Secondary text */
```

Helpers: `.game-card` (hover lift, off-screen skip for large grids),
`.truncate-title` (ellipsis with full-text `title` tooltip), `.dcgl-scroll`
(thin overlay-style scrollbar with stable gutter).

## Shell Layout (`App.tsx`)

Fixed chrome with a single scroll region per view:

```structure
App
├── Header (logo, "Sync catalogue", "Stats")
├── Tabs ("Catalogue" / "My library")
├── main (flex-1, no scrolling of its own)
│   └── CataloguePage | LibraryPage (own .dcgl-scroll grid wrapper)
├── Footer (in-flow status bar: cache / no-win / library / running)
├── StatsModal
└── Toasts
```

The footer stats refetch every 5 seconds. `StatsModal` shows the same four
counts on demand and closes on Escape.

## Catalogue Tab

**Components:** `CataloguePage`, `GameCard`, `SearchBar`

- `SearchBar` is fixed above the grid with a debounced (250 ms) query and
  a "Showing X of Y games in catalogue" counter.
- Only games with at least one Windows executable are listed. Each card
  shows artwork (Discord CDN, initial-letter fallback), the name, the
  first 3 executable variants (`+N more` tooltip for the rest), and an
  "In library" marker when applicable.
- **Select:** single click toggles selection (ring highlight); games already in the library are dimmed, skip selection, and offer only an "Already in library" menu entry.
- **Add:** double-click adds one game; the floating "Add N selected"
  pill adds the whole selection; right-click opens Add to library.
- Backend failures render the backend's error message with a retry
  button instead of an empty grid.

## Library Tab

**Components:** `LibraryPage`, `LibraryCard`

Toolbar: library count plus **Refresh**, **Repair**, and **Stop all**
buttons. The **Repair** button opens a confirmation dialog that warns
file deletion is permanent and cannot be undone; confirming runs the
backend repair (see [Library Maintenance](./library-maintenance.md)) and
toasts the summary.

Cards show artwork, a running/stopped dot, game name, and process name:

- **Toggle start/stop:** double-click, Enter/Space, or the context-menu
  action.
- **Remove:** context-menu action with a confirmation dialog. The game
  is stopped first, then its files and database rows are deleted.
- Card statuses refresh via the backend `library_changed` event after every mutation; only the footer/stats counts poll (every 5 seconds).

## Data Layer

Each module pairs a thin service (bridge calls) with React Query hooks:

```structure
catalogue-service / library-service   # bridge.<method>() calls
useCatalogue / useLibrary             # useQuery + useMutation wrappers
ui-store (Zustand)                    # tab, search, selected ids,
                                      # stats modal, toasts, counts
```

`useDcglEvents` subscribes to the backend `library_changed` event
and invalidates the matching query keys, so library changes propagate
without polling. Start/stop/add/remove/repair results arrive as direct
return values and surface as a single toast each.

Game IDs are strings on the wire (see [Bridge](./bridge.md): ID
Contract). Selection state, React keys, and mutation arguments all use
the string form; never coerce IDs through `Number`.

## Accessibility and Keyboard Support

- Tabs use `role=tab` with `aria-selected`; cards use `role=checkbox`
  (`aria-checked`) in the catalogue and `role=button` in the library.
- Catalogue cards support arrow-key navigation between cards.
- All dialogs trap the Escape key to close and label themselves with
  `aria-label`. Focus-visible outlines use the accent color.
