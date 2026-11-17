import assert from 'node:assert/strict';
import { test } from 'node:test';

import { JOTTINGS_KEY, enqueue, flushOutbox, readOutbox, remove, type KeyValueStore } from './outbox.ts';
import type { PendingCapture } from './types.ts';

function memoryStore(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    async getItem(k) {
      return data.get(k) ?? null;
    },
    async setItem(k, v) {
      data.set(k, v);
    },
  };
}

const capture = (clientId: string): PendingCapture => ({
  clientId,
  workspaceId: 1,
  kind: 'idea',
  body: `idea ${clientId}`,
  photos: [],
  createdAt: new Date().toISOString(),
});

test('enqueue replaces captures with the same clientId', async () => {
  const store = memoryStore();
  await enqueue(store, capture('a'));
  await enqueue(store, { ...capture('a'), body: 'edited' });
  const items = await readOutbox(store);
  assert.equal(items.length, 1);
  assert.equal(items[0].body, 'edited');
});

test('corrupt storage reads as empty', async () => {
  const store = memoryStore();
  await store.setItem('forgecapture.outbox.v1', '{nope');
  assert.deepEqual(await readOutbox(store), []);
});

test('flush sends everything and empties the queue', async () => {
  const store = memoryStore();
  await enqueue(store, capture('a'));
  await enqueue(store, capture('b'));
  const res = await flushOutbox(store, async (c) => c.clientId.toUpperCase(), () => false);
  assert.deepEqual(res.sent.map((s) => s.result), ['A', 'B']);
  assert.deepEqual(await readOutbox(store), []);
});

test('server error skips to next item; network error stops the flush', async () => {
  const store = memoryStore();
  for (const id of ['a', 'b', 'c', 'd']) await enqueue(store, capture(id));
  const netErr = Object.assign(new Error('offline'), { net: true });
  const res = await flushOutbox(
    store,
    async (c) => {
      if (c.clientId === 'a') throw Object.assign(new Error('422 bad'), { status: 422 });
      if (c.clientId === 'c') throw netErr;
      return c.clientId;
    },
    (e) => (e as { net?: boolean }).net === true,
  );
  assert.deepEqual(res.sent.map((s) => s.result), ['b']);
  const left = await readOutbox(store);
  assert.deepEqual(left.map((c) => c.clientId), ['a', 'c', 'd']);
  assert.equal(left[0].lastError, '422 bad');
  assert.equal(left[0].lastErrorStatus, 422);
  assert.equal(left[2].lastError, undefined); // never attempted
});

test('jottings live under their own key and can be removed', async () => {
  const store = memoryStore();
  await enqueue(store, { ...capture('j1'), workspaceId: null }, JOTTINGS_KEY);
  await enqueue(store, capture('o1'));
  assert.deepEqual((await readOutbox(store, JOTTINGS_KEY)).map((c) => c.clientId), ['j1']);
  assert.deepEqual((await readOutbox(store)).map((c) => c.clientId), ['o1']);
  await remove(store, 'j1', JOTTINGS_KEY);
  assert.deepEqual(await readOutbox(store, JOTTINGS_KEY), []);
});
