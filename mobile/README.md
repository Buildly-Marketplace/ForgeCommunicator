# Forge Capture (iOS + Android)

A small phone app for jotting down ideas and bugs in seconds and turning them into
real, estimated work in **Buildly Labs**.

```
 ✎ Capture          ✨ Estimate                    ✓ Review              → Labs
 text + photos  →   AI breaks it into features,  → keep / skip items,  →  backlog items in Labs,
 + screenshots      issues & tasks with points,    pick Dev / AI /        artifacts in Forge,
                    dev hours and AI-agent hours   AI+Dev per item        AI items → coding agent
```

## Free vs. Pro

| | Free | Pro (subscription or one-time) |
|---|---|---|
| Jot notes, photos & screenshots | ✅ kept on this phone, no account needed | ✅ |
| Save & sync to your account | – | ✅ |
| AI breakdown into features/issues + estimates | – | ✅ |
| Send to Buildly Labs / hand off to coding agents | – | ✅ |
| Browse Labs products & backlog | ✅ with a free account | ✅ |

Free notes can be uploaded and estimated later, one tap each, after going Pro.
Purchases are tied to the Forge account (not the device), so they work on every phone the
user signs in on, and can be restored.

**Enforcement is server-side.** `POST /ideas`, `/refine`, `/submit` and `PATCH /ideas` return
`402 subscription_required` without an active entitlement. The server learns about purchases only
from RevenueCat's API (after a purchase via `/billing/sync`, and from webhooks for renewals,
cancellations, refunds and expirations), never from the app's own claims.

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
| Paywall: status, purchase sync, RevenueCat webhook, admin grants | `app/routers/billing_api.py` |
| Entitlement logic + RevenueCat client | `app/services/capture_billing.py` |

App layout (Expo Router, routes in `src/app/`):

| Path | Screen |
|---|---|
| `src/app/login.tsx` | Sign in with Buildly Labs or email; custom server URL |
| `src/app/(tabs)/index.tsx` | Capture |
| `src/app/(tabs)/inbox.tsx` | My ideas (+ pending uploads) |
| `src/app/(tabs)/products.tsx` | Labs products |
| `src/app/(tabs)/settings.tsx` | Workspace switcher, connections, sign out |
| `src/app/idea/[id].tsx` | Breakdown review & send to Labs |
| `src/app/paywall.tsx` | Plans (prices from the stores), buy, restore, manage |
| `src/app/product/[id].tsx` | Product backlog |
| `src/lib/` | API client, session, offline outbox, free notes, RevenueCat wrapper |

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

## Payments setup (App Store, Google Play, RevenueCat)

Apple and Google require their own in-app billing for unlocking app features, so purchases go
through the stores. [RevenueCat](https://www.revenuecat.com) wraps both stores, validates receipts
and tells our server what each user owns.

1. **Create the products** in App Store Connect and Google Play Console, for example:
   - `capture_pro_monthly`: auto-renewing subscription
   - `capture_pro_yearly`: auto-renewing subscription
   - `capture_pro_lifetime`: one-time, non-consumable purchase

   You set prices in the store consoles. The app shows whatever the stores return, with no
   prices in code.
2. **In RevenueCat:** add both apps, create the entitlement `capture_pro` and attach all three
   products. Then create an offering marked **current** with Monthly / Annual / Lifetime packages.
3. **Server env:**
   - `REVENUECAT_SECRET_API_KEY`: the secret key.
   - `REVENUECAT_WEBHOOK_AUTH`: a random string.
   - `REVENUECAT_ENTITLEMENT_ID`: only if you didn't name it `capture_pro`.
4. **RevenueCat webhook:** URL `<BASE_URL>/mobile/v1/billing/revenuecat/webhook`, with the
   Authorization header set to the same `REVENUECAT_WEBHOOK_AUTH` value.
5. **App config** (`app.json` → `expo.extra`):
   - `revenuecatIosKey` / `revenuecatAndroidKey`: the *public* SDK keys, safe to ship.
   - `termsUrl` / `privacyUrl`: required by Apple for subscriptions, and shown on the paywall.
6. **Comps & self-hosting:**
   - Platform admins and `CAPTURE_FREE_EMAILS` always have access.
   - Admins can grant access with `POST /mobile/v1/billing/grants {"email": ...}`.
   - Self-hosted installs that don't sell the app can set `CAPTURE_PAYWALL_ENABLED=false`.

Real purchases need a development or store build (`eas build`), because Expo Go can't make
store purchases. Test with App Store sandbox accounts and Play license testers.

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
