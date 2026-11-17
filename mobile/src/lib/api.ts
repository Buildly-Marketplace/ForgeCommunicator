import type {
  Agent,
  BacklogItem,
  Bootstrap,
  Builder,
  Idea,
  PendingCapture,
  Priority,
  Product,
  SubmitResult,
  User,
} from './types';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
  /** True when the request never got a response (offline, DNS, timeout). */
  get isNetwork() {
    return this.status === 0;
  }
}

export function normalizeServerUrl(raw: string): string {
  let url = raw.trim().replace(/\/+$/, '');
  if (url && !/^https?:\/\//i.test(url)) url = `https://${url}`;
  return url;
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    // FastAPI validation errors: [{loc, msg}]
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  }
  return `Request failed (${status})`;
}

export class Api {
  constructor(
    public serverUrl: string,
    private token: string | null,
  ) {}

  private async request<T>(path: string, init: RequestInit = {}, timeoutMs = 30000): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    if (init.body && !(init.body instanceof FormData)) headers['Content-Type'] = 'application/json';

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    let res: Response;
    try {
      res = await fetch(`${this.serverUrl}/mobile/v1${path}`, {
        ...init,
        headers: { ...headers, ...(init.headers as Record<string, string>) },
        signal: controller.signal,
      });
    } catch {
      throw new ApiError('Can’t reach the server. Check your connection.', 0);
    } finally {
      clearTimeout(timer);
    }
    if (res.status === 204) return undefined as T;
    const text = await res.text();
    let body: unknown = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = null;
    }
    if (!res.ok) throw new ApiError(errorMessage(body, res.status), res.status);
    return body as T;
  }

  // Auth -------------------------------------------------------------------
  login(email: string, password: string, deviceName?: string) {
    return this.request<{ token: string; user: User }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password, device_name: deviceName }),
    });
  }
  register(email: string, password: string, displayName: string, deviceName?: string) {
    return this.request<{ token: string; user: User }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name: displayName, device_name: deviceName }),
    });
  }
  oauthStart(provider: 'buildly' | 'google') {
    return this.request<{ auth_url: string; state: string }>(
      `/auth/oauth/${provider}/start?app_scheme=forgecapture`,
    );
  }
  me() {
    return this.request<User>('/me');
  }
  logout() {
    return this.request<void>('/auth/logout', { method: 'POST' });
  }

  // Labs / products --------------------------------------------------------
  bootstrap() {
    return this.request<Bootstrap>('/capture/bootstrap');
  }
  products(workspaceId: number) {
    return this.request<Product[]>(`/workspaces/${workspaceId}/products`);
  }
  syncProducts(workspaceId: number) {
    return this.request<unknown>(`/workspaces/${workspaceId}/products/sync`, { method: 'POST' }, 120000);
  }
  productItems(productId: number, type?: string) {
    return this.request<BacklogItem[]>(`/products/${productId}/items${type ? `?type=${type}` : ''}`);
  }
  agents(workspaceId: number) {
    return this.request<Agent[]>(`/workspaces/${workspaceId}/agents`);
  }

  // Ideas ------------------------------------------------------------------
  createIdea(capture: PendingCapture) {
    const form = new FormData();
    form.append('workspace_id', String(capture.workspaceId));
    form.append('kind', capture.kind);
    form.append('body', capture.body);
    form.append('client_id', capture.clientId);
    if (capture.title) form.append('title', capture.title);
    if (capture.productId) form.append('product_id', String(capture.productId));
    if (capture.context) form.append('context', JSON.stringify(capture.context));
    for (const photo of capture.photos) {
      // React Native's FormData accepts {uri, name, type} file descriptors
      form.append('files', photo as unknown as Blob);
    }
    return this.request<Idea>('/ideas', { method: 'POST', body: form }, 120000);
  }
  ideas(workspaceId?: number) {
    return this.request<Idea[]>(`/ideas${workspaceId ? `?workspace_id=${workspaceId}` : ''}`);
  }
  idea(id: number) {
    return this.request<Idea>(`/ideas/${id}`);
  }
  updateIdea(
    id: number,
    patch: {
      title?: string | null;
      body?: string;
      kind?: string;
      product_id?: number | null;
      items?: { id: string; selected?: boolean; builder?: Builder; title?: string; priority?: Priority }[];
    },
  ) {
    return this.request<Idea>(`/ideas/${id}`, { method: 'PATCH', body: JSON.stringify(patch) });
  }
  deleteIdea(id: number) {
    return this.request<void>(`/ideas/${id}`, { method: 'DELETE' });
  }
  refineIdea(id: number) {
    // AI breakdowns can take a while
    return this.request<Idea>(`/ideas/${id}/refine`, { method: 'POST' }, 150000);
  }
  submitIdea(id: number, opts: { push_to_labs?: boolean; agent_integration_id?: number | null }) {
    return this.request<SubmitResult>(
      `/ideas/${id}/submit`,
      { method: 'POST', body: JSON.stringify(opts) },
      150000,
    );
  }
}
