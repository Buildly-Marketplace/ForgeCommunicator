// Offline outbox: captures are saved locally first, then flushed to the server.
// Pure logic lives here (testable with node --test); storage is injected.

import type { PendingCapture } from './types';

export interface KeyValueStore {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

const KEY = 'forgecapture.outbox.v1';

export async function readOutbox(store: KeyValueStore): Promise<PendingCapture[]> {
  try {
    const raw = await store.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function writeOutbox(store: KeyValueStore, items: PendingCapture[]): Promise<void> {
  await store.setItem(KEY, JSON.stringify(items));
}

export async function enqueue(store: KeyValueStore, capture: PendingCapture): Promise<PendingCapture[]> {
  const items = (await readOutbox(store)).filter((c) => c.clientId !== capture.clientId);
  items.push(capture);
  await writeOutbox(store, items);
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
      remaining.push({ ...capture, lastError: e instanceof Error ? e.message : String(e) });
    }
  }
  await writeOutbox(store, remaining);
  return { sent, remaining };
}
