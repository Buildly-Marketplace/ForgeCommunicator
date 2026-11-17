import AsyncStorage from '@react-native-async-storage/async-storage';
import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { Api, ApiError, normalizeServerUrl } from './api';
import { enqueue, flushOutbox, readOutbox } from './outbox';
import type { Bootstrap, CaptureWorkspace, Idea, PendingCapture, User } from './types';

const TOKEN_KEY = 'forgecapture.token';
const SERVER_KEY = 'forgecapture.server';
const WORKSPACE_KEY = 'forgecapture.workspace';

export const DEFAULT_SERVER_URL: string =
  (Constants.expoConfig?.extra?.defaultServerUrl as string | undefined) ?? 'https://comms.buildly.io';

interface SessionState {
  ready: boolean;
  serverUrl: string;
  token: string | null;
  user: User | null;
  bootstrap: Bootstrap | null;
  workspace: CaptureWorkspace | null;
  pending: PendingCapture[];
  api: Api;
  signIn(serverUrl: string, token: string): Promise<void>;
  signOut(): Promise<void>;
  setServerUrl(url: string): Promise<void>;
  selectWorkspace(id: number): Promise<void>;
  refreshBootstrap(): Promise<void>;
  /** Save locally, then try to send. Returns the server Idea if it went through. */
  capture(c: PendingCapture): Promise<Idea | null>;
  flush(): Promise<number>;
}

const SessionContext = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);
  const [serverUrl, setServer] = useState(DEFAULT_SERVER_URL);
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [workspaceId, setWorkspaceId] = useState<number | null>(null);
  const [pending, setPending] = useState<PendingCapture[]>([]);

  const api = useMemo(() => new Api(serverUrl, token), [serverUrl, token]);

  const loadBootstrap = useCallback(
    async (client: Api) => {
      const [me, boot] = await Promise.all([client.me(), client.bootstrap()]);
      setUser(me);
      setBootstrap(boot);
      const saved = Number(await AsyncStorage.getItem(WORKSPACE_KEY));
      const ws = boot.workspaces.find((w) => w.id === saved) ?? boot.workspaces[0];
      setWorkspaceId(ws?.id ?? null);
    },
    [],
  );

  // Restore session on launch
  useEffect(() => {
    (async () => {
      const [savedToken, savedServer] = await Promise.all([
        SecureStore.getItemAsync(TOKEN_KEY),
        AsyncStorage.getItem(SERVER_KEY),
      ]);
      const url = savedServer || DEFAULT_SERVER_URL;
      setServer(url);
      setPending(await readOutbox(AsyncStorage));
      if (savedToken) {
        setToken(savedToken);
        try {
          await loadBootstrap(new Api(url, savedToken));
        } catch (e) {
          if (e instanceof ApiError && e.status === 401) {
            await SecureStore.deleteItemAsync(TOKEN_KEY);
            setToken(null);
          }
          // Offline: stay signed in so captures still work and queue up
        }
      }
      setReady(true);
    })();
  }, [loadBootstrap]);

  const signIn = useCallback(
    async (url: string, newToken: string) => {
      const normalized = normalizeServerUrl(url);
      await SecureStore.setItemAsync(TOKEN_KEY, newToken);
      await AsyncStorage.setItem(SERVER_KEY, normalized);
      setServer(normalized);
      setToken(newToken);
      await loadBootstrap(new Api(normalized, newToken));
    },
    [loadBootstrap],
  );

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // token may already be invalid; sign out locally regardless
    }
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setBootstrap(null);
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

  const refreshBootstrap = useCallback(() => loadBootstrap(api), [api, loadBootstrap]);

  const flush = useCallback(async () => {
    if (!token) return 0;
    const { sent, remaining } = await flushOutbox(
      AsyncStorage,
      (c) => api.createIdea(c),
      (e) => e instanceof ApiError && e.isNetwork,
    );
    setPending(remaining);
    return sent.length;
  }, [api, token]);

  const capture = useCallback(
    async (c: PendingCapture) => {
      setPending(await enqueue(AsyncStorage, c));
      const { sent, remaining } = await flushOutbox(
        AsyncStorage,
        (item) => api.createIdea(item),
        (e) => e instanceof ApiError && e.isNetwork,
      );
      setPending(remaining);
      return sent.find((s) => s.capture.clientId === c.clientId)?.result ?? null;
    },
    [api],
  );

  // Opportunistically flush anything queued while offline
  useEffect(() => {
    if (token && pending.length) flush().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const workspace = bootstrap?.workspaces.find((w) => w.id === workspaceId) ?? null;

  const value: SessionState = {
    ready,
    serverUrl,
    token,
    user,
    bootstrap,
    workspace,
    pending,
    api,
    signIn,
    signOut,
    setServerUrl,
    selectWorkspace,
    refreshBootstrap,
    capture,
    flush,
  };
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used inside SessionProvider');
  return ctx;
}
