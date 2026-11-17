import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { Api, ApiError, normalizeServerUrl } from './api';
import { JOTTINGS_KEY, OUTBOX_KEY, enqueue, flushOutbox, readOutbox, remove } from './outbox';
import { deletePhotos, persistPhotos } from './photos';
import * as purchases from './purchases';
import type { BillingStatus, Bootstrap, CaptureWorkspace, Idea, PendingCapture, User } from './types';

const TOKEN_KEY = 'forgecapture.token';
const SERVER_KEY = 'forgecapture.server';
const WORKSPACE_KEY = 'forgecapture.workspace';

export const DEFAULT_SERVER_URL: string =
  (Constants.expoConfig?.extra?.defaultServerUrl as string | undefined) ?? 'https://comms.buildly.io';

export type CaptureOutcome =
  | { kind: 'uploaded'; idea: Idea }
  | { kind: 'queued' } // Pro, but offline — will upload later
  | { kind: 'local' }; // free note kept on this phone

interface SessionState {
  ready: boolean;
  serverUrl: string;
  token: string | null;
  user: User | null;
  bootstrap: Bootstrap | null;
  workspace: CaptureWorkspace | null;
  access: BillingStatus | null;
  /** Can save to the server / estimate / send to Labs */
  isPro: boolean;
  pending: PendingCapture[];
  jottings: PendingCapture[];
  api: Api;
  signIn(serverUrl: string, token: string): Promise<void>;
  signOut(): Promise<void>;
  setServerUrl(url: string): Promise<void>;
  selectWorkspace(id: number): Promise<void>;
  refreshBootstrap(): Promise<void>;
  refreshAccess(sync?: boolean): Promise<BillingStatus | null>;
  /** Pro: upload (or queue). Free: keep it on the phone. */
  capture(c: PendingCapture): Promise<CaptureOutcome>;
  saveJotting(c: PendingCapture): Promise<void>;
  deleteJotting(clientId: string): Promise<void>;
  /** Move a free note to the server (Pro only). */
  uploadJotting(clientId: string, productId?: number): Promise<Idea | null>;
  flush(): Promise<number>;
}

const SessionContext = createContext<SessionState | null>(null);
const isNetworkError = (e: unknown) => e instanceof ApiError && e.isNetwork;

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [serverUrl, setServer] = useState(DEFAULT_SERVER_URL);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [access, setAccess] = useState<BillingStatus | null>(null);
  const [workspaceId, setWorkspaceId] = useState<number | null>(null);
  const [pending, setPending] = useState<PendingCapture[]>([]);
  const [jottings, setJottings] = useState<PendingCapture[]>([]);

  const api = useMemo(() => new Api(serverUrl, token), [serverUrl, token]);
  const isPro = !!token && !!access?.active;

  const loadAccount = useCallback(async (client: Api) => {
    const [me, boot, billing] = await Promise.all([client.me(), client.bootstrap(), client.billingStatus()]);
    setUser(me);
    setBootstrap(boot);
    setAccess(billing);
    purchases.identify(billing.app_user_id);
    const saved = Number(await AsyncStorage.getItem(WORKSPACE_KEY));
    const ws = boot.workspaces.find((w) => w.id === saved) ?? boot.workspaces[0];
    setWorkspaceId(ws?.id ?? null);
  }, []);

  // Restore session on launch. Signing in is optional: free notes work without an account.
  useEffect(() => {
    (async () => {
      const [savedToken, savedServer] = await Promise.all([
        SecureStore.getItemAsync(TOKEN_KEY),
        AsyncStorage.getItem(SERVER_KEY),
      ]);
      const url = savedServer || DEFAULT_SERVER_URL;
      setServer(url);
      setPending(await readOutbox(AsyncStorage, OUTBOX_KEY));
      setJottings(await readOutbox(AsyncStorage, JOTTINGS_KEY));
      if (savedToken) {
        setToken(savedToken);
        try {
          await loadAccount(new Api(url, savedToken));
        } catch (e) {
          if (e instanceof ApiError && e.status === 401) {
            await SecureStore.deleteItemAsync(TOKEN_KEY);
            setToken(null);
          }
          // Offline: stay signed in; captures queue up
        }
      }
      setReady(true);
    })();
  }, [loadAccount]);

  const signIn = useCallback(
    async (url: string, newToken: string) => {
      const normalized = normalizeServerUrl(url);
      await SecureStore.setItemAsync(TOKEN_KEY, newToken);
      await AsyncStorage.setItem(SERVER_KEY, normalized);
      setServer(normalized);
      setToken(newToken);
      await loadAccount(new Api(normalized, newToken));
    },
    [loadAccount],
  );

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // token may already be invalid; sign out locally regardless
    }
    await purchases.forget();
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setBootstrap(null);
    setAccess(null);
  }, [api]);

  const setServerUrl = useCallback(async (url: string) => {
    const normalized = normalizeServerUrl(url);
    await AsyncStorage.setItem(SERVER_KEY, normalized);
    setServer(normalized);
  }, []);

  const selectWorkspace = useCallback(async (id: number) => {
    await AsyncStorage.setItem(WORKSPACE_KEY, String(id));
    setWorkspaceId(id);
  }, []);

  const refreshBootstrap = useCallback(() => loadAccount(api), [api, loadAccount]);

  const refreshAccess = useCallback(
    async (sync = false) => {
      if (!token) return null;
      const status = sync ? await api.billingSync() : await api.billingStatus();
      setAccess(status);
      return status;
    },
    [api, token],
  );

  const workspace = bootstrap?.workspaces.find((w) => w.id === workspaceId) ?? null;

  const flush = useCallback(async () => {
    if (!token) return 0;
    const { sent, remaining } = await flushOutbox(AsyncStorage, (c) => api.createIdea(c), isNetworkError);
    setPending(remaining);
    if (remaining.some((c) => c.lastErrorStatus === 402)) refreshAccess().catch(() => undefined);
    return sent.length;
  }, [api, token, refreshAccess]);

  const saveJotting = useCallback(async (c: PendingCapture) => {
    const photos = await persistPhotos(c.clientId, c.photos);
    setJottings(await enqueue(AsyncStorage, { ...c, photos }, JOTTINGS_KEY));
  }, []);

  const deleteJotting = useCallback(async (clientId: string) => {
    setJottings(await remove(AsyncStorage, clientId, JOTTINGS_KEY));
    deletePhotos(clientId);
  }, []);

  const send = useCallback(
    async (c: PendingCapture): Promise<CaptureOutcome> => {
      setPending(await enqueue(AsyncStorage, c, OUTBOX_KEY));
      const { sent, remaining } = await flushOutbox(AsyncStorage, (item) => api.createIdea(item), isNetworkError);
      setPending(remaining);
      const idea = sent.find((s) => s.capture.clientId === c.clientId)?.result;
      if (idea) return { kind: 'uploaded', idea };
      const failed = remaining.find((r) => r.clientId === c.clientId);
      if (failed?.lastErrorStatus === 402) {
        // Subscription lapsed server-side: keep it as a free note instead
        setPending(await remove(AsyncStorage, c.clientId, OUTBOX_KEY));
        await saveJotting({ ...c, lastError: undefined, lastErrorStatus: undefined });
        refreshAccess().catch(() => undefined);
        return { kind: 'local' };
      }
      return { kind: 'queued' };
    },
    [api, refreshAccess, saveJotting],
  );

  const capture = useCallback(
    async (c: PendingCapture): Promise<CaptureOutcome> => {
      if (!isPro || c.workspaceId == null) {
        await saveJotting(c);
        return { kind: 'local' };
      }
      return send(c);
    },
    [isPro, saveJotting, send],
  );

  const uploadJotting = useCallback(
    async (clientId: string, productId?: number) => {
      const jotting = jottings.find((j) => j.clientId === clientId);
      if (!jotting || !isPro || !workspace) return null;
      const chosenProduct = productId ?? jotting.productId;
      if (chosenProduct == null) throw new Error('Pick a product for this note first');
      setJottings(await remove(AsyncStorage, clientId, JOTTINGS_KEY));
      const outcome = await send({
        ...jotting,
        productId: chosenProduct,
        // a product picked now belongs to the current workspace
        workspaceId: productId != null ? workspace.id : (jotting.workspaceId ?? workspace.id),
      });
      if (outcome.kind === 'uploaded') {
        deletePhotos(clientId);
        return outcome.idea;
      }
      return null;
    },
    [jottings, isPro, workspace, send],
  );

  // Opportunistically flush anything queued while offline
  useEffect(() => {
    if (isPro && pending.length) flush().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPro]);

  const value: SessionState = {
    ready,
    serverUrl,
    token,
    user,
    bootstrap,
    workspace,
    access,
    isPro,
    pending,
    jottings,
    api,
    signIn,
    signOut,
    setServerUrl,
    selectWorkspace,
    refreshBootstrap,
    refreshAccess,
    capture,
    saveJotting,
    deleteJotting,
    uploadJotting,
    flush,
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used inside SessionProvider');
  return ctx;
}
