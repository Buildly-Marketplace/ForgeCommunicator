// Shapes returned by ForgeCommunicator's /mobile/v1 API (app/routers/capture_api.py).

export type IdeaKind = 'idea' | 'bug' | 'feedback';
export type IdeaStatus = 'draft' | 'refining' | 'refined' | 'submitted' | 'failed';
export type Builder = 'dev' | 'ai' | 'pair';
export type Priority = 'low' | 'medium' | 'high' | 'critical';

export interface User {
  id: number;
  email: string;
  display_name: string;
  avatar_url?: string | null;
}

export interface CaptureWorkspace {
  id: number;
  name: string;
  labs_connected: boolean;
  default_product_uuid?: string | null;
}

export interface Bootstrap {
  workspaces: CaptureWorkspace[];
  user_labs_connected: boolean;
  ai_configured: boolean;
  uploads_enabled: boolean;
  labs_web_url: string;
}

export interface Product {
  id: number;
  workspace_id: number;
  name: string;
  description?: string | null;
  labs_uuid?: string | null;
  color?: string | null;
  icon_url?: string | null;
  open_features: number;
  open_issues: number;
}

export interface BacklogItem {
  id: number;
  type: string;
  title: string;
  status: string;
  priority?: string | null;
  severity?: string | null;
  labs_uuid?: string | null;
  assignee_agent?: string | null;
  created_at: string;
}

export interface Agent {
  id: number;
  name: string;
  provider: string;
  avatar_emoji?: string | null;
}

export interface Estimate {
  points: number;
  human_hours: number;
  ai_hours: number;
  confidence: 'low' | 'medium' | 'high';
}

export interface BreakdownItem {
  id: string;
  type: 'feature' | 'issue' | 'task';
  title: string;
  description: string;
  acceptance_criteria: string[];
  priority: Priority;
  estimate: Estimate;
  builder: Builder;
  rationale: string;
  selected: boolean;
}

export interface Breakdown {
  title: string;
  summary: string;
  items: BreakdownItem[];
  questions: string[];
  totals: { points: number; human_hours: number; ai_hours: number };
  engine: string;
}

export interface Attachment {
  url: string;
  filename?: string;
  content_type?: string;
  size?: number;
}

export interface SubmittedItem {
  artifact_id: number;
  item_id: string;
  type: string;
  title: string;
  builder: Builder;
  labs_uuid?: string | null;
  assigned_agent?: string | null;
}

export interface Idea {
  id: number;
  workspace_id: number;
  product_id?: number | null;
  product_name?: string | null;
  client_id?: string | null;
  kind: IdeaKind;
  title?: string | null;
  body: string;
  status: IdeaStatus;
  attachments: Attachment[];
  context?: Record<string, string> | null;
  breakdown?: Breakdown | null;
  error?: string | null;
  submitted_items: SubmittedItem[];
  created_at: string;
  updated_at: string;
}

export interface SubmitResult {
  idea: Idea;
  created: SubmittedItem[];
  labs_pushed: number;
  warnings: string[];
}

/** A capture that hasn't reached the server yet (offline / server error). */
export interface PendingCapture {
  clientId: string;
  workspaceId: number;
  productId?: number | null;
  kind: IdeaKind;
  title?: string;
  body: string;
  context?: Record<string, string>;
  photos: { uri: string; name: string; type: string }[];
  createdAt: string;
  lastError?: string;
}
