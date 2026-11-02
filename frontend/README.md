# Pathwise AI — Frontend

Modern React application built with TanStack Start, Vite, TypeScript, and Tailwind CSS.

## Features & Routes
- **`/` (Home)**: Landing presentation, value proposition, public verified tools modal, and embedded live creator preview.
- **`/login` (Auth)**: Sign-in / registration screen with role-based routing (Admin vs. Creator).
- **`/app` (Workspace)**: Creator workspace featuring interactive multi-turn interview, brief review, AI creation path generation, prompt copying, tool links, and finished step handoff rewrites.
- **`/admin` (Admin Console)**: Tool catalog management with status filtering (`draft`, `verified`, `hidden`), AI documentation ingestion, and monetization affiliate URL management.

## Environment Variables
Create `.env` based on `.env.example`:
```ini
VITE_API_URL="http://localhost:8000"
VITE_ADMIN_TOKEN="pathwise-admin-secret-token"
VITE_ADMIN_EMAIL="admin@pathwise.ai"
```

## Running Locally
```bash
npm install
npm run dev
```

## Building for Production
```bash
npm run build
```
