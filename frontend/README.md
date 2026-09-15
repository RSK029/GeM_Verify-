# GeMVerify — frontend

React 18 + Vite + TypeScript. Two portals (bidder, administration) against the
GeMVerify API.

## Run

Start the backend first (see `../backend`), then:

```bash
cp .env.example .env
npm install
npm run dev          # http://localhost:5173
```

`VITE_API_BASE` defaults to `http://localhost:8000/api`. The backend already
allows `http://localhost:5173` with credentials.

| Script | |
|---|---|
| `npm run dev` | dev server |
| `npm run build` | typecheck + production build to `dist/` |
| `npm run typecheck` | types only |

## Notes for anyone picking this up

- **The session is an httpOnly cookie.** Every request sends
  `credentials: 'include'`; nothing auth-related touches `localStorage`. There
  is no role selector at login — the backend resolves the role and the app
  routes on `user.role`.
- **PDFs are fetched and blobbed**, never `<iframe src>`, which would 401.
  Object URLs are revoked on unmount (`hooks/useDocumentBlob.ts`).
- **Scores are weak signal.** Lists sort by status and findings before score
  (`lib/severity.ts`); a percentage is never the largest thing on a card. A bid
  can score 100.0 on every metric and still be the most serious case in the set.
- `GET /bids/{id}/explanation` 404s until narration runs. That is a generating
  state, not an error.

`HANDOVER.md` lists backend issues found, contract divergences and what is
stubbed.
