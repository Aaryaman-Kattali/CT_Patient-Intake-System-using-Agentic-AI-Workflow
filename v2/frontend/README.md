# Intake assistant V2: frontend

**Demo only. Synthetic data only.** React + TypeScript + Vite.

```bash
npm ci                 # install from package-lock.json
npm run gen:api        # regenerate API types from the backend (never hand-write them)
npm run dev            # http://localhost:5173 (API at VITE_API_URL, default http://localhost:8000)
npm run typecheck && npm test          # types and component tests
npx playwright install chromium        # once
npm run e2e            # end-to-end: real backend + rule-based fake understander, no Gemini
```

- **API types** come from the backend's OpenAPI schema (`openapi.json` → `src/api/schema.d.ts`).
  `npm run check:api` (in CI) fails if they are out of date.
- **Wording**: every word comes from the backend (`GET /ui/text`, the field registry and each
  turn). The only text in this code is one offline message, identical to the backend's.
- **Accessibility**: one question per screen as the page heading; focus moves to it on every
  new turn and it is announced in a polite live region; "Reading your answer…" only after
  1 second; no motion at all; the same buttons in the same places; "I'm not sure" always last;
  nothing changes until the user acts; adjustable text size; large touch targets; works on a
  phone. Playwright runs axe (WCAG 2.2 A/AA) on every screen type and a keyboard-only walkthrough.
- **Session**: the intake token is kept in `localStorage`, so closing the tab and coming back
  resumes on the same device. Another device uses the resume code.
- The end-to-end tests save screenshots of each screen type to `screenshots/`.
