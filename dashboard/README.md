# Helios SDR Dashboard

Next.js 15 frontend for the Helios SDR agent. Talks to the Python FastAPI backend at `NEXT_PUBLIC_API_URL`.

## Setup

```bash
cd dashboard
npm install
cp .env.example .env.local
# Edit .env.local if your API runs somewhere other than localhost:8000
npm run dev
```

Open http://localhost:3000 and log in with your `DASHBOARD_PASSWORD` (from `../.env`).

## Requirements

- Node 20+
- The Python FastAPI backend running (see `../README.md` for backend setup and `make api`)

## Stack

- Next.js 15 (App Router) + React 19
- TypeScript strict
- Tailwind CSS v4 (CSS-first config, no `tailwind.config.ts`)
- shadcn/ui primitives
- Zustand (auth) + SWR (data)
- recharts, react-markdown, lucide-react, sonner
