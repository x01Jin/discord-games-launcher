# UI

The frontend is a React single-page app inside a pywebview native window. All
backend access goes through the typed `window.pywebview.api` bridge
(`launcher/bridge.py`, see [Bridge](./bridge.md)). React 19, Vite, and Tailwind
CSS 4; React Query holds server state and Zustand holds UI state.

## Layout

A fixed two-column shell. The left rail is the only persistent chrome; each page
owns its header, toolbar, and scroll region.

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

Tokens live in `frontend/src/index.css` under `@theme`. The main ones:

| Token | Value | Use |
| --- | --- | --- |
| `--color-base` | `#1e1f22` | Sidebar, inputs |
| `--color-canvas` | `#313338` | Main content |
| `--color-raised` | `#2b2d31` | Panels, dialogs |
| `--color-ink` / `--color-muted` / `--color-subtle` | greys | Text levels |
| `--color-accent` | `#5865f2` | Primary action, focus, selection |

Utilities: `scroll-thin` (8 px overlay scrollbar with a stable gutter),
`truncate-1`, `row-skip` (`content-visibility: auto` for long lists).

The palette, the 4 px control radius, and the 34 to 56 px row heights are
Discord's. The app sits next to the client, so borrowing its greys reads as part
of it.

## Shared components

| Component | Role |
| --- | --- |
| `primitives.tsx` | Button, IconButton, Checkbox, Chip, StatusDot, ProgressBar, Switch, Skeleton, EmptyState |
| `PageHeader.tsx` | `PageHeader` and `Toolbar` |
| `SearchField.tsx` | Search input with icon, clear button, Escape |
| `GameArt.tsx` | Art tile: quest artwork, then app icon, then initials |
| `Dialog.tsx` | Modal with Escape, backdrop, focus handoff |
| `Menu.tsx` | Cursor-anchored menu in a portal, flips at viewport edges |
| `Sidebar.tsx` | Navigation and live client state |
| `Toasts.tsx` | Bottom-right stack, three at a time |
| `icons.tsx` | Inline SVG set, no icon package |

## Quests

The default view. It reads the quest list from the running Discord client (see
[Quests](./quests.md)).

- Header: counts of open, running, and finished quests, the orb balance when the
  client reports one, and Refresh.
- Toolbar (`modules/quests/components/QuestToolbar.tsx`): All / Play / Watch
  filter, a reward filter (All rewards, Orbs, Avatar decoration, In-game), a sort
  menu (Suggested, Expiring soon, Most orbs, Most progress), a "Show finished"
  switch, and a "Set up silent start" button while the launch argument is not
  installed.
- Rows: checkbox on rows that can be queued, art (video thumbnail for watch
  quests), quest name, one metadata line, reward chip, time left (amber inside
  24 h), progress bar once enrolled, and the action the backend chose: Run, Stop,
  Watch, Done, or Unsupported. Video rows carry a Video chip; a mobile video
  quest is labelled "Mobile video". A queued row shows a Queued chip, and the
  video being credited shows a Watching chip with Stop as its action.
- Selection (`modules/quests/hooks/useQuestSelection.ts`): every unfinished play
  or video quest has a checkbox, accepted or not. Start selected accepts the
  quests that need it and queues them in two lanes: games run one after another,
  videos are credited in the background. An unaccepted row shows a "Not accepted"
  chip.
- Filters (`modules/quests/lib/filters.ts`) drive the reward and kind predicates
  and the sort order.
- Disconnected: one panel that states the situation, shows what the client
  reported, and offers the single useful action. The copy is short because the
  panel sits in a ~530 px column.

## Running

Games and videos in flight, plus what comes next.

- Header: counts the play run, the video, and queued quests separately; Refresh
  and Clear queue (which stops the video and empties the queue, leaving the play
  run alone).
- Now: the video being credited and the running play quest as full rows with
  Stop. One play run at a time, so Now holds at most two rows.
- Up next: queued quests grouped into Videos and Games, both always shown with a
  count. Each row has its position, art, name, kind, reward chip, progress, and
  Move up / Move down / Remove; moving a row reorders that lane only.
- Empty states: Discord not connected, and nothing moving, both with Open Quests.

## Catalogue

- Header: playable game count and reload.
- Toolbar: search (220 ms debounce), selection summary, add actions.
- Rows: select checkbox, art, name, up to two executable chips plus a count, and
  an Add button. In-library rows are dimmed and not selectable.
- Paging: `useInfiniteQuery` with 200 games per page, loading the next page as
  the window nears the end of what is loaded.
- Windowing: `useVirtualRows` mounts only the visible rows at a fixed 48 px
  height.
- Keyboard: Tab reaches rows, Arrow Up/Down moves between them, Space toggles,
  Enter adds.

## Library

- Header: game count, running count, Refresh, Repair, Stop all.
- Rows: art, name, a second line with a state dot, the process name, Running or
  Stopped, Start/Stop, and a menu with Start/Stop and Remove.
- Repair opens a confirmation that says the deletion is permanent (see
  [Library maintenance](./library-maintenance.md)).
- Rows refresh from the backend `library_changed` event; there is no polling
  beyond a 20 s stats refresh.

## Settings

Three panels in one centered column capped at 880 px, so a wide window gets
equal gutters. On a narrow window the column fills the body.

- Discord client: the channel and version from `status()`, and where the
  loopback endpoint is: `Port 9222` when connected, "Running without it" when the
  client is up but was started before the switch, or "Discord is closed".
- Launch patch: the flag in mono, a status pill (`On for 4 of 4 launch entries`,
  `Off. Discord starts normally.`, amber when partial), one card per entry with
  its kind, a Patched/Original chip, the location, and the command line it will
  run. **Remove patch** opens a danger dialog naming how many entries go back;
  **Turn on** appears while any entry is unpatched.
- Removal and re-application use `disable_silent_mode` / `enable_silent_mode`,
  the same calls as the Quests panel, so the page only reflects state. Both
  invalidate `["silent-mode"]` and `["quests"]`.
- Quest runs: a Play activity segmented control (**Show activity** / **Private**,
  `aria-pressed`) and a pause-between-quests field (0 to 30 minutes). Both save
  through `set_quest_prefs` and apply to the next run without a restart.
- A footnote says removal restores the exact original command lines and that an
  already-open Discord keeps its endpoint until it is closed.

## Data layer

```structure
modules/<feature>/services   # bridge calls
modules/<feature>/hooks      # useQuery / useMutation / useInfiniteQuery
shared/hooks/useQuests       # quest list + client status, shared with the sidebar
shared/hooks/useStats        # backend counts for the rail
shared/store/ui-store        # page, search, selection, show-finished, toasts
```

`useQuests` is shared: the sidebar reads the same query key, so the connection
line and the page never disagree and the client is probed once.

## Performance

- Catalogue filtering and paging happen in SQL; the frontend never receives more
  than one page at a time.
- Off-screen rows use `content-visibility: auto` on top of windowing.
- Icons are lazy and fade in over their initials, so a slow CDN never leaves an
  empty box.
- Queries are invalidated by backend events instead of polling.
- `prefers-reduced-motion` disables animation and smooth scrolling.

## Accessibility

- Nav items expose `aria-current`; dialogs use `role="dialog"` with
  `aria-modal`, move focus to the panel, and keep Tab inside it.
- Menus move focus to their first item, cycle with Arrow Up/Down, Home, and End,
  and close on Escape with focus back on the button.
- Checkboxes and switches keep a visible 16 px box but accept clicks in a larger
  area. Helper text uses the subtle grey, which stays above 4.5:1 on raised
  panels.
- Axe-core 4.10.2 reports no WCAG 2 A or AA violations on any page.
- Rows are real buttons or checkboxes, reachable by Tab, with visible
  `:focus-visible` rings in the accent colour.
- Progress bars carry `aria-valuenow` and an accessible label; toasts use
  `aria-live="polite"`.
