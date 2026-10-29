# UI

## Overview

The frontend is a React single-page app rendered inside a pywebview native
window. All backend access goes through the typed `window.pywebview.api`
bridge (`launcher/bridge.py`); the contract is
documented in [Bridge](./bridge.md).

- Stack: React 19, Vite, Tailwind CSS 4
- Theme: Discord's dark palette with a single accent
- State: React Query for server state, Zustand for UI state

## Layout

Fixed two-column shell. The left rail is the only persistent chrome; each page
owns its own header, toolbar, and scroll region.

```structure
App
├── Sidebar (228px, bg-base)
│   ├── brand
│   ├── nav: Quests / Running / Catalogue / Library  (counts where useful)
│   ├── Settings  (pinned above the client state)
│   └── client state: Discord connection, running fakes
├── main (bg-canvas)
│   ├── PageHeader    (title, subtitle, actions)
│   ├── Toolbar       (search, filters, selection actions)
│   └── scroll region (rows)
└── Toasts (bottom right)
```

The last visited page is remembered in `localStorage` (`dcgl.page`).

## Theme

Tokens live in `frontend/src/index.css` under `@theme`:

| Token            | Value                   | Use                           |
| ---------------- | ----------------------- | ----------------------------- |
| `--color-base`   | `#1e1f22`               | Sidebar, inputs               |
| `--color-canvas` | `#313338`               | Main content                  |
| `--color-raised` | `#2b2d31`               | Panels, dialogs               |
| `--color-hover`  | `#35373c`               | Row hover                     |
| `--color-active` | `#404249`               | Selected nav, pressed control |
| `--color-line`   | rgba(255,255,255,.06)   | Hairline borders              |
| `--color-ink`    | `#f2f3f5`               | Primary text                  |
| `--color-muted`  | `#b5bac1`               | Secondary text                |
| `--color-subtle` | `#949ba4`               | Tertiary text, icons          |
| `--color-accent` | `#5865f2`               | Primary action, focus, select |

Utilities: `scroll-thin` (8 px overlay scrollbar with a stable gutter),
`truncate-1`, `row-skip` (`content-visibility: auto` for long lists).

The palette, the 4 px control radius, and the 34-56 px row heights are
Discord's. The app sits next to the client, so borrowing its greys reads as
part of the ecosystem rather than as a themed web page.

## Shared components

| Component        | Role                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------ |
| `primitives.tsx` | Button, IconButton, Checkbox, Chip, StatusDot, ProgressBar, Switch, Skeleton, EmptyState |
| `PageHeader.tsx` | `PageHeader` and `Toolbar`                                                           |
| `SearchField.tsx`| Search input with icon, clear button, Escape                                          |
| `GameArt.tsx`    | Art tile: quest artwork, then app icon, then initials                                 |
| `Dialog.tsx`     | Modal with Escape, backdrop, focus handoff                                            |
| `Menu.tsx`       | Cursor-anchored menu in a portal, flips at the viewport edges                        |
| `Sidebar.tsx`    | Navigation and live client state                                                      |
| `Toasts.tsx`     | Bottom-right stack, three at a time                                                   |
| `icons.tsx`      | Inline SVG set; no icon package                                                       |

## Quests

The default view. It reads the quest list from the running Discord client (see
[Quests](./quests.md)).

- Header: counts of open, running, and finished quests, the orb balance when
  the client reports one, and Refresh.
- Toolbar: All / Play / Watch filter, a reward filter (All rewards, Orbs,
  Avatar decoration, In-game), a sort menu (Suggested, Expiring soon, Most
  orbs, Most progress), a "Show finished" switch, and a "Set up silent start"
  button while the launch argument is not installed. The count shows how many
  rows are visible, plus the total only when the filter hides some.
- Rows: checkbox (only on rows that can be queued), art (video thumbnail for
  watch quests), quest name, one metadata line, reward chip, time left (amber
  inside 24 h), progress bar once enrolled, and one action chosen by the
  backend: Run, Stop, Watch (green), Done, or Unsupported. The
  metadata line joins the kind label (non-play quests), the game name when it
  adds something to the title, and the executable, with no repeated words: a
  play quest on "Call of Duty: Modern Warfare 4" reads `sp26-cod.exe`. Video
  rows also carry a Video chip, and a mobile video quest is labelled "Mobile
  video" because it finishes from here rather than on the phone. A queued row
  shows a Queued chip; the video being credited shows an accent Watching chip
  and its action becomes Stop, so the wait can be ended from the row.
- Selection: every unfinished play or video quest gets a checkbox, accepted or
  not. Start selected accepts the quests that need it and queues them in two
  lanes: games run one after another, videos are credited in the background.
  Run and Watch accept a quest themselves, so there is no Accept button; an
  unaccepted row shows a "Not accepted" chip in the meantime.
  The lanes do not block each other, so a video starts while a game keeps
  running. The queue bar names what is running or which video is playing, with
  Skip video and Clear queue.
- Disconnected: one panel that states the situation, shows what the client
  reported, and offers the single useful action. With silent mode off it lists
  the three steps of the setup; with the setup done but the client still
  started before it, the panel says one restart finishes it. The copy is short
  because the panel sits in a ~530 px column.

## Running

Games and videos in flight, plus what comes next.

- Header: subtitle counts the play run, the video, and queued quests
  separately; Refresh and Clear queue (which stops the video and empties the
  queue, leaving the play run alone).
- Now: the video being credited and the running play quest, as full quest rows
  with Stop. A video row carries the Watching chip. One play run at a time, so
  Now holds at most two active rows.
- Up next: the queued quests grouped into their two lanes, Videos and Games,
  both always shown with a count, so an empty lane says so instead of
  disappearing. Each row has its position, art, name, kind, reward chip,
  progress, and Move up / Move down / Remove. Moving a row reorders that lane
  only. The Now section is not split: the video and the games run together.
- Empty states: Discord not connected (with Open Quests) and nothing moving
  (with Open Quests). The sidebar entry shows the count of active plus queued
  quests.

## Catalogue

- Header: playable game count and reload.
- Toolbar: search (220 ms debounce), selection summary, add actions.
- Rows: select checkbox, art, name, up to two executable chips plus a
  count, and an Add button. In-library rows are dimmed and not selectable.
- Paging: `useInfiniteQuery` with 200 games per page; the next page loads
  when the window approaches the end of what is already loaded.
- Windowing: `useVirtualRows` mounts only the visible rows at a fixed
  48 px height, so the list stays fast as it grows.
- Keyboard: Tab reaches rows, Arrow Up/Down moves between them, Space
  toggles, Enter adds.

## Library

- Header: game count, running count, Refresh, Repair, Stop all.
- Rows: art, name, a second line with a state dot, the process name, and
  Running or Stopped, Start/Stop, and a menu with Start/Stop and Remove.
- The Repair button opens a confirmation dialog that says the deletion is permanent
  (see [Library Maintenance](./library-maintenance.md)).
- Rows refresh from the backend `library_changed` event; there is no polling
  beyond a 20 s stats refresh.

## Settings

Three panels in one centered column capped at 880 px inside the page body, so
a wide window gets equal gutters rather than a short strip of content beside a
large empty pane. On a narrow window the column fills the body. No state of
their own beyond one dialog flag.

- Discord client: the channel and version from `status()`, and where the
  loopback endpoint is: `Port 9222` when connected, "Running without it" when
  the client is up but was started before the switch, or "Discord is closed".
- Launch patch: the flag in mono, a status pill (`On for 4 of 4 launch
  entries`, `Off. Discord starts normally.`, amber when partial), one card per
  entry with its kind, a Patched/Original chip, the location, and the command
  line it will run. **Remove patch** opens a danger dialog that names how many
  entries go back; **Turn on** appears while any entry is unpatched.
- Removal and re-application use the same two bridge calls as the Quests panel
  (`disable_silent_mode` / `enable_silent_mode`), so the page only reflects
  state. Both mutations invalidate `["silent-mode"]` and `["quests"]`, which is
  what flips the cards, the sidebar dot, and the Quests toolbar button.
- Quest runs: a Play activity segmented control (**Show activity** / **Private**,
  `aria-pressed`) and a pause-between-quests field (0 to 30 minutes). Both save
  through `set_quest_prefs` and apply to the next run without a restart. Two
  buttons rather than a dropdown because there are two modes and both need their
  consequence spelled out; the panel copy says no game launches either way.
- A footnote says the removal restores the exact original command lines and that
  an already-open Discord keeps its endpoint until it is closed, because the
  patch only takes effect on the next start.

## Data layer

```structure
modules/<feature>/services   # bridge calls
modules/<feature>/hooks      # useQuery / useMutation / useInfiniteQuery
shared/hooks/useQuests       # quest list + client status, shared with the sidebar
shared/hooks/useStats        # backend counts for the rail
shared/store/ui-store        # page, search, selection, show-finished, toasts
```

`useQuests` is deliberately shared: the sidebar reads the same query key, so
the connection line and the page never disagree and the client is probed once.

## Performance notes

- Catalogue filtering and paging happen in SQL; the frontend never receives
  more than one page at a time.
- Off-screen rows use `content-visibility: auto` on top of windowing.
- Icons are lazy and fade in over their initials, so a slow CDN never leaves
  an empty box.
- Queries are invalidated by backend events instead of polling.
- `prefers-reduced-motion` disables animation and smooth scrolling.

## Accessibility

- Nav items expose `aria-current`; dialogs use `role="dialog"` with
  `aria-modal`, move focus to the panel, and keep Tab inside it.
- Menus move focus to their first item on open, cycle with Arrow Up/Down,
  Home, and End, and close on Escape with focus back on the button that opened
  them.
- Checkboxes and switches keep a visible 16 px box but accept clicks in a
  larger area around it. Helper text uses the subtle grey rather than the
  faint one, which stays above 4.5:1 on raised panels.
- Axe-core 4.10.2 reports no WCAG 2 A or AA violations on any page.
- Rows are real buttons or checkboxes, reachable by Tab, with visible
  `:focus-visible` rings in the accent colour.
- Progress bars carry `aria-valuenow` and an accessible label.
- Toasts use `aria-live="polite"`.
