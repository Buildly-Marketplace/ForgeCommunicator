# Forge Capture (iOS + Android)

A small phone app for jotting down ideas and bugs in seconds and turning them into
real, estimated work in **Buildly Labs**.

```
 ✎ Capture          ✨ Estimate                    ✓ Review              → Labs
 text + photos  →   AI breaks it into features,  → keep / skip items,  →  backlog items in Labs,
 + screenshots      issues & tasks with points,    pick Dev / AI /        artifacts in Forge,
                    dev hours and AI-agent hours   AI+Dev per item        AI items → coding agent
```

## What it does

- **Capture** – type a note, snap a photo (whiteboard, sketch) or attach screenshots. Tag it as an
  *Idea*, *Bug* (with "which app?") or *Feedback*, optionally for a specific Labs product.
  Device model / OS are attached automatically to help with bug reports.
- **Works offline** – captures are saved on the phone first and upload when you’re back online
  (the server de-duplicates retries).
- **Estimate** – the server’s AI turns the note into 1–6 features/issues/tasks, each with acceptance
  criteria, Fibonacci story points, hours for a developer vs. an AI coding agent, and a suggested
  builder (Developer, AI agent, or AI + Dev).
- **Review & send** – skip items you don’t want, change who builds what, optionally hand AI work to a
  registered coding agent (Claude Code, Codex, …), then send. Items land in Labs and in Forge.
- **Browse products** – see your Labs products with open feature/issue counts and their backlog;
  sync from Labs on demand.

## Architecture

The app talks only to a **ForgeCommunicator** server (`/mobile/v1/*`), which already holds the
Labs OAuth connection, AI provider keys and file storage. Nothing secret lives on the phone except
the user’s session token (kept in the iOS Keychain / Android Keystore via `expo-secure-store`).

| Server piece | File |
|---|---|
| Capture endpoints (ideas, refine, submit, products, agents) | `app/routers/capture_api.py` |
| AI breakdown + estimates (and non-AI fallback) | `app/services/idea_refiner.py` |
| `Idea` model | `app/models/idea.py` |
| Sign-in (email / Buildly Labs OAuth) | `app/routers/mobile_api.py` |

App layout (Expo Router, routes in `src/app/`):

| Path | Screen |
|---|---|
| `src/app/login.tsx` | Sign in with Buildly Labs or email; custom server URL |
| `src/app/(tabs)/index.tsx` | Capture |
| `src/app/(tabs)/inbox.tsx` | My ideas (+ pending uploads) |
| `src/app/(tabs)/products.tsx` | Labs products |
| `src/app/(tabs)/settings.tsx` | Workspace switcher, connections, sign out |
| `src/app/idea/[id].tsx` | Breakdown review & send to Labs |
| `src/app/product/[id].tsx` | Product backlog |
| `src/lib/` | API client, session, offline outbox |

## Server setup

On the ForgeCommunicator server:

1. **AI estimates** – set `IDEA_AI_PROVIDER` (`anthropic` or `openai`) and `IDEA_AI_API_KEY`
   (optionally `IDEA_AI_MODEL`). Without these, the workspace’s first active AI agent is used; with
   neither, a rough non-AI estimate is produced so the flow still works.
2. **Photos** – configure S3/Spaces storage (`STORAGE_*`). Without it, photo buttons are disabled.
3. **Labs** – users who sign in with *Continue with Buildly Labs* get their Labs token stored
   automatically. A workspace can also be connected in workspace settings. Set a default Labs
   product for the workspace, or pick a product when capturing.
4. **Labs OAuth redirect** – the Labs OAuth client must allow
   `<BASE_URL>/mobile/v1/auth/oauth/buildly/callback` as a redirect URI.

## Run it

```bash
cd mobile
npm install
npx expo start          # scan the QR code with Expo Go, or press i / a for a simulator
```

The default server is `https://comms.buildly.io` (see `extra.defaultServerUrl` in `app.json`);
change it on the sign-in screen under “Server”. For a local server use your machine’s LAN IP,
e.g. `http://192.168.1.20:8000`.

Checks:

```bash
npm run typecheck
npm test                # offline-outbox unit tests (node:test)
```

## Build for the stores

Uses [EAS Build](https://docs.expo.dev/build/introduction/) – no local Xcode/Android Studio needed:

```bash
npx eas-cli@latest build --profile preview --platform all     # internal test builds
npx eas-cli@latest build --profile production --platform all
npx eas-cli@latest submit --platform ios                      # / android
```

Bundle IDs: `io.buildly.forgecapture` (iOS and Android). URL scheme: `forgecapture://`.

## Ideas for next steps

- **Share extension** – “Share to Forge Capture” from any app’s share sheet / screenshot editor
  (needs a development build with a share-intent module).
- **Voice notes** – dictate an idea; transcribe on the server.
- **Vision** – send screenshots to the AI so it can read error messages and UI directly
  (today the AI sees the note text and attachment names; images are linked in Labs items).
- **Push notifications** when an agent or developer picks up / ships an item.
