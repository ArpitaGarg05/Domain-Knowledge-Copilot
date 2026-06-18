# Stitch Design System and Missing-Screen Blueprints

This document translates the supplied Stitch exports into an implementation
contract for the Streamlit application. The exports remain the source of truth;
these notes make their recurring decisions explicit and reusable.

## Design direction

The interface is a dark, enterprise research environment: dense enough for
technical work, quiet enough for long reading sessions, and punctuated by
electric indigo for intelligence and emerald for system health.

The product should feel like one continuous instrument rather than a set of
independent web pages. Authentication uses a centered secure-access console.
The authenticated product uses a fixed desktop command rail and a fluid content
canvas. Cards are separated through tonal layering, thin borders, and subtle
glow instead of conventional drop shadows.

## Tokens

### Color

| Token | Value | Usage |
| --- | --- | --- |
| `background` | `#051424` | Main application canvas |
| `surface-lowest` | `#010f1f` | Sidebar, input wells, deepest cards |
| `surface-low` | `#0d1c2d` | Secondary panels and controls |
| `surface` | `#122131` | Main cards and top bar |
| `surface-high` | `#1c2b3c` | Hover and selected surfaces |
| `surface-highest` | `#273647` | Chips, compact metadata surfaces |
| `text` | `#d4e4fa` | Primary copy |
| `text-muted` | `#c7c4d8` | Body and supporting copy |
| `outline` | `#918fa1` | Secondary icons and metadata |
| `outline-subtle` | `#464555` | Borders and dividers |
| `primary` | `#c3c0ff` | Active text, focus, citation accents |
| `primary-strong` | `#4f46e5` | Primary buttons and active navigation |
| `success` | `#4edea3` | Indexed, connected, healthy |
| `warning` | `#ffb695` | Processing warnings and attention |
| `error` | `#ffb4ab` | Destructive actions and errors |

### Typography

- Display and body: Geist.
- Metadata, status, filenames, IDs, and chunk previews: JetBrains Mono.
- Page title: 40/48, weight 700, tracking -0.02em.
- Section title: 32/40, weight 600.
- Body: 16/24.
- Supporting body: 14/20.
- Technical label: 12/16, weight 600, uppercase, tracking 0.05em.
- Mobile titles step down to 24/32.

### Shape and spacing

- Base spacing unit: 4px.
- Common gaps: 8, 12, 16, 24, and 32px.
- Controls: 8px radius.
- Cards: 12px radius.
- Hero/input containers: 16px radius.
- Pills: full radius.
- Desktop rail: 280px.
- Reading column: 900px maximum.

### Depth and motion

- Glass panels use translucent navy, a 20px backdrop blur, and a 1px outline.
- Focus uses an indigo bloom rather than vertical movement.
- Interactive controls scale to 0.98 on press.
- Hover transitions run for 160–220ms.
- Status dots use a slow pulse.
- Initial page sections use a short fade/translate entrance.
- Motion is disabled when `prefers-reduced-motion` is enabled.

## Reusable primitives

1. `App shell`
   Fixed command rail on desktop; Streamlit's collapsed sidebar drawer on
   narrow screens. The rail carries brand, primary navigation, context, and
   user identity.
2. `Page header`
   Monospaced eyebrow, strong title, concise supporting copy, optional action.
3. `Glass card`
   Tonal surface, subtle top highlight, 12px radius, thin border.
4. `Metric cell`
   Uppercase mono label, prominent value, compact context line.
5. `Status badge`
   Dot or icon plus uppercase mono label; emerald for indexed/healthy.
6. `Primary action`
   Solid indigo, high contrast, 8px radius, glow on hover.
7. `Secondary action`
   Low surface, thin outline, primary-color hover.
8. `Technical input`
   Deep input well, mono label, indigo border/glow on focus.
9. `Document row`
   File icon, filename, indexing metadata, status, size, and compact actions.
10. `Citation card`
    Visually separate from chat bubbles through a left indigo rail, mono source
    header, page badge, clamped preview, and native expand/collapse disclosure.
11. `Conversation row`
    Corpus chip, title/preview, timestamp, message count, and resume action.
12. `Empty state`
    Dashed technical boundary, restrained icon, one direct next action.

## Missing-screen blueprints

### Corpus Detail

```text
┌ command rail ┐  CORPUS / ACTIVE
│ navigation   │  Corpus title                         [Upload PDF]
│ corpus list  │  Description and indexed status
│ user         │
└──────────────┘  [Documents] [Pages] [Chunks] [Storage]
                   ┌─────────────────────┬──────────────┐
                   │ Document inventory  │ Upload zone  │
                   │ file / pages / size │ index health │
                   │ status / timestamp  │ storage mix  │
                   └─────────────────────┴──────────────┘
```

The inventory is the dominant surface. Statistics are compact and scannable,
while upload remains visible without overwhelming document management.

### Citation Panel

```text
Assistant response
┌──────────────────────────────────────────────────────┐
│ SOURCES · 3                         RETRIEVAL COMPLETE │
│ ▌ [01] filename.pdf   PAGE 12   CHUNK_124       [⌄]  │
│ ▌ Clamped preview of the retrieved source...         │
│ ▌ expanded source text when opened                   │
└──────────────────────────────────────────────────────┘
```

Citations remain attached to the answer but never resemble another chat
message. Indigo rails identify evidence; emerald communicates retrieval state.
Native disclosure controls provide keyboard-accessible expansion.

### Chat History

```text
CHAT ARCHIVE
Previous conversations
[ Search conversations........................ ] [Corpus filter]

[ALL 18] [THIS WEEK 7] [CORPORA 4]

TODAY
┌ corpus chip  Conversation title               14:32 ┐
│ Last question or answer preview          [Resume →] │
└─────────────────────────────────────────────────────┘
```

Rows optimize scanning over decoration. Search covers message content and
corpus names. Resume selects the corpus and returns to the existing chat,
preserving the application's current conversation model.

### Settings

```text
ACCOUNT CONTROL
Settings
┌ Profile ────────────────────┐ ┌ Interface ───────────┐
│ Avatar / name / email       │ │ Density              │
│ account identity            │ │ citation behavior    │
└─────────────────────────────┘ │ motion                │
┌ Security ───────────────────┐ └──────────────────────┘
│ session / API connection    │ ┌ Data & session ──────┐
│ logout                      │ │ local state / logout  │
└─────────────────────────────┘ └──────────────────────┘
```

Settings use the same card and label hierarchy as corpus management. Current
backend-supported identity is shown faithfully; UI preferences live in
Streamlit session state and affect rendering immediately.

## Responsive behavior

- At 900px and below, cards collapse to one column.
- The desktop rail becomes Streamlit's drawer; navigation remains fully usable.
- Page padding drops from 32px to 16px.
- Metric grids reduce from four columns to two, then one.
- Document and conversation metadata wrap beneath titles.
- Chat uses the full available width while maintaining readable line lengths.

