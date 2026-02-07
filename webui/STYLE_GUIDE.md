# Cassette Futurism Style Guide

> **Alien / Blade Runner terminal aesthetic** — dark industrial hardware, amber phosphor CRT glow, dense monospaced readouts, chunky beveled panels.

---

## Color Palette

### Backgrounds

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-bg-primary` | `#0a0a0c` | Page background, input fields |
| `--color-bg-secondary` | `#111114` | Cards, panels, modals |
| `--color-bg-tertiary` | `#18181c` | Table headers, form cards |
| `--color-bg-elevated` | `#1e1e24` | Hover states, nested surfaces |

### Sidebar / Chrome

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-bg-dark` | `#08080a` | Sidebar background |
| `--color-bg-dark-secondary` | `#0f0f12` | Active nav item bg |
| `--color-bg-dark-tertiary` | `#1a1a1e` | Sidebar borders |

### Text — Amber Phosphor

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-text-primary` | `#d4a04a` | Body text, labels |
| `--color-text-secondary` | `#8b7340` | Descriptions, dim labels |
| `--color-text-muted` | `#5a4c2e` | Placeholders, disabled |
| `--color-text-inverse` | `#0a0a0c` | Text on amber backgrounds |

### Accent — Bright Amber

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-accent` | `#e8a020` | Active elements, borders, buttons |
| `--color-accent-hover` | `#f0b840` | Hover state |
| `--color-accent-muted` | `rgba(232,160,32,0.12)` | Subtle tinted backgrounds |
| `--color-accent-glow` | `rgba(232,160,32,0.4)` | Box-shadow / text-shadow glow |

### Status Colors — Phosphor Hues

| Token | Hex | Glow rgba |
|-------|-----|-----------|
| `--color-success` | `#33cc33` | `rgba(51,204,51,0.4)` |
| `--color-warning` | `#e8a020` | `rgba(232,160,32,0.4)` |
| `--color-error` | `#ff3333` | `rgba(255,51,51,0.4)` |
| `--color-info` | `#3399ff` | `rgba(51,153,255,0.4)` |

### Borders

| Token | Hex | Usage |
|-------|-----|-------|
| `--color-border` | `#2a2520` | Default panel/table borders |
| `--color-border-strong` | `#3a3228` | Hover borders, table header underline |

---

## Typography

### Font Stack

```css
/* Primary — everything */
font-family: 'IBM Plex Mono', monospace;

/* Display — large stat numbers, titles */
font-family: 'VT323', monospace;
```

**Google Fonts import:**
```
https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=VT323&display=swap
```

### Rules

- **All headings**: `text-transform: uppercase; letter-spacing: 0.1em`
- **Nav labels / section headers**: `letter-spacing: 0.15–0.2em`
- **No sans-serif fonts** — everything is monospaced
- **Body size**: `15px` base (`html { font-size: 15px }`)
- **Table headers**: `0.5625–0.625rem`, `font-weight: 600`
- **Body text**: `0.8125rem`

---

## Geometry

### Border Radius

```css
--border-radius: 2px;    /* all components */
--border-radius-lg: 2px; /* same — no rounding */
```

> **Rule: Never exceed 2px border-radius.** Hard edges = hardware. Rounded = SaaS.

### Spacing Scale

| Context | Padding |
|---------|---------|
| Cards | `1rem` |
| Table cells | `0.625rem 0.75rem` |
| Buttons | `0.5rem 1rem` |
| Small buttons | `0.3rem 0.625rem` |
| Form inputs | `0.625rem 0.75rem` |
| Sidebar nav items | `0.5rem 0.875rem` |
| Section gaps | `0.75rem` |

> **Rule: Keep spacing tight.** This is a terminal, not a marketing page.

---

## Shadows & Depth

### Panel Bezel (recessed CRT screen)

```css
box-shadow: inset 0 2px 4px rgba(0,0,0,0.4),
            inset 0 -1px 0 rgba(212,160,74,0.06);
```

### Input Fields (deep recess)

```css
box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
```

### Glow (active elements)

```css
box-shadow: 0 0 12px rgba(232,160,32,0.4);
```

> **Rule: No drop shadows.** Use `inset` shadows only — panels are recessed behind bezels, not floating.

---

## Effects

### CRT Scanline Overlay

Applied globally via `body::after`. Fine horizontal lines across the entire viewport:

```css
body::after {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.06) 2px,
    rgba(0, 0, 0, 0.06) 4px
  );
  mix-blend-mode: multiply;
}
```

### Text Glow

Apply to page titles, active nav items, stat numbers, and status badges:

```css
text-shadow: 0 0 8px rgba(232, 160, 32, 0.4);  /* amber */
text-shadow: 0 0 6px rgba(51, 204, 51, 0.4);    /* green status */
text-shadow: 0 0 6px rgba(255, 51, 51, 0.4);    /* red alert */
```

### LED Pulse Animation

For the app title and active indicators — slow breathe like a hardware LED:

```css
@keyframes led-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
/* Usage: animation: led-pulse 3s ease-in-out infinite; */
```

### Alert Pulse

For error/critical badges — red glow throb:

```css
@keyframes alert-pulse {
  0%, 100% { opacity: 1; text-shadow: 0 0 6px rgba(255,51,51,0.6); }
  50% { opacity: 0.8; text-shadow: 0 0 12px rgba(255,51,51,0.8); }
}
```

### Selection Color

```css
::selection {
  background: rgba(232, 160, 32, 0.3);
  color: #f0b840;
}
```

---

## Component Patterns

### Buttons — Outlined Hardware Switches

```css
.btn {
  background: transparent;
  border: 2px solid var(--color-accent);
  color: var(--color-accent);
  font-family: 'IBM Plex Mono', monospace;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  border-radius: 2px;
}

.btn:hover {
  background: var(--color-accent);
  color: var(--color-text-inverse);
  box-shadow: 0 0 12px rgba(232, 160, 32, 0.3);
}
```

> Buttons are **outlined by default**, filled on hover — like pressing a physical toggle.

### Status Badges — LED Indicators

```css
.badge {
  padding: 0.125rem 0.5rem;
  border: 1px solid;
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  text-shadow: 0 0 6px currentColor;  /* glow matches text color */
}
```

### Cards — Recessed Panels

```css
.card {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 2px;
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.4),
              inset 0 -1px 0 rgba(212,160,74,0.06);
}

/* Top edge amber highlight (bezel light catch) */
.card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg,
    transparent, rgba(232,160,32,0.15), transparent);
}
```

### Tables — Dense Terminal Output

```css
.table {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.8125rem;
  border-collapse: collapse;
}

.table th {
  font-size: 0.625rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--color-text-muted);
  background: var(--color-bg-tertiary);
  border-bottom: 1px solid var(--color-border-strong);
}

.table td {
  border-bottom: 1px solid var(--color-border);
}

.table tbody tr:hover {
  background: rgba(232, 160, 32, 0.04);
}
```

### Inputs — Terminal Fields

```css
input {
  background: var(--color-bg-primary);
  border: 1px solid var(--color-border);
  color: var(--color-accent);  /* typed text is amber */
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);
}

input:focus {
  border-color: var(--color-accent);
  box-shadow: inset 0 2px 4px rgba(0,0,0,0.5),
              0 0 8px rgba(232,160,32,0.2);
}
```

### Sidebar — Control Panel

```css
.sidebar {
  background: #08080a;
  border-right: 1px solid var(--color-accent);  /* amber divider line */
  box-shadow: 4px 0 16px rgba(0,0,0,0.5);
}

.nav-item.active {
  border-left: 3px solid var(--color-accent);
  color: var(--color-accent);
  text-shadow: 0 0 8px rgba(232,160,32,0.4);
}
```

### Scrollbar

```css
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: var(--color-bg-primary); }
::-webkit-scrollbar-thumb {
  background: var(--color-border-strong);
  border-radius: 0;  /* square thumb */
}
```

---

## Do / Don't

| ✅ Do | ❌ Don't |
|------|---------|
| Use `inset` shadows for depth | Use drop shadows |
| Keep borders `1px solid` | Use dashed or dotted borders |
| Set `border-radius: 2px` max | Use rounded corners (`6px+`) |
| Use monospace fonts everywhere | Mix in sans-serif body fonts |
| Apply `text-shadow` glow on active states | Leave active elements without glow |
| Keep spacing tight and dense | Use generous whitespace |
| Make buttons outlined by default | Use filled/solid button defaults |
| Use `uppercase + letter-spacing` on labels | Use sentence case on UI chrome |
| Animate LEDs with slow `3s` breathe | Use fast flashy animations |
