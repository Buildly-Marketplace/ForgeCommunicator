// Offline outbox: captures are saved locally first, then flushed to the server.
// Pure logic lives here (testable with node --test); storage is injected.

import type { PendingCapture } from './types';

export interface KeyValueStore {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

/** Pro captures waiting to upload. */
export const OUTBOX_KEY = 'forgecapture.outbox.v1';
/** Free notes kept only on this phone. */
export const JOTTINGS_KEY = 'forgecapture.jottings.v1';

export async function readOutbox(store: KeyValueStore, key: string = OUTBOX_KEY): Promise<PendingCapture[]> {
  try {
    const raw = await store.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function writeOutbox(
  store: KeyValueStore,
  items: PendingCapture[],
  key: string = OUTBOX_KEY,
): Promise<void> {
  await store.setItem(key, JSON.stringify(items));
}

export async function enqueue(
  store: KeyValueStore,
  capture: PendingCapture,
  key: string = OUTBOX_KEY,
): Promise<PendingCapture[]> {
  const items = (await readOutbox(store, key)).filter((c) => c.clientId !== capture.clientId);
  items.push(capture);
  await writeOutbox(store, items, key);
  return items;
}

export async function remove(store: KeyValueStore, clientId: string, key: string): Promise<PendingCapture[]> {
  const items = (await readOutbox(store, key)).filter((c) => c.clientId !== clientId);
  await writeOutbox(store, items, key);
  return items;
}

export interface FlushResult<T> {
  sent: { capture: PendingCapture; result: T }[];
  remaining: PendingCapture[];
}

/**
 * Try to send every queued capture, oldest first. Captures that fail stay queued
 * with their error recorded. A network failure stops the flush early (no point
 * hammering a dead connection); server-side errors move on to the next item.
 * The server de-duplicates on clientId, so retries are safe.
 */
export async function flushOutbox<T>(
  store: KeyValueStore,
  send: (c: PendingCapture) => Promise<T>,
  isNetworkError: (e: unknown) => boolean,
): Promise<FlushResult<T>> {
  const queue = await readOutbox(store);
  const sent: FlushResult<T>['sent'] = [];
  const remaining: PendingCapture[] = [];
  let offline = false;
  for (const capture of queue) {
    if (offline) {
      remaining.push(capture);
      continue;
    }
    try {
      sent.push({ capture, result: await send(capture) });
    } catch (e) {
      offline = isNetworkError(e);
      const status = (e as { status?: unknown }).status;
      remaining.push({
        ...capture,
        lastError: e instanceof Error ? e.message : String(e),
        lastErrorStatus: typeof status === 'number' ? status : undefined,
      });
    }
  }
  await writeOutbox(store, remaining);
  return { sent, remaining };
}
