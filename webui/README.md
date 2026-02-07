# WebUI

React-based dashboard for Coalmine. Built with Vite and TypeScript.

## Setup

```bash
cd webui
npm install
```

## Development

```bash
npm run dev
```

This starts the Vite dev server with hot reload. The API is expected at `http://localhost:8000`.

## Production Build

```bash
npm run build
```

Output goes to `webui/dist/`, which the FastAPI app serves at `/ui`.

## Stack

- **React 18** with TypeScript
- **Vite** for bundling
- **TanStack Query** for data fetching
- **React Router** for client-side routing
- **Vanilla CSS** with CRT/terminal aesthetic (see [STYLE_GUIDE.md](STYLE_GUIDE.md))

## Directory Structure

```
webui/
├── src/
│   ├── components/   # Reusable UI components
│   ├── hooks/        # Custom React hooks (data fetching)
│   ├── pages/        # Route-level page components
│   ├── App.tsx       # Root component with routing
│   └── main.tsx      # Entry point
├── public/           # Static assets
├── index.html        # HTML template
└── vite.config.ts    # Vite configuration
```
