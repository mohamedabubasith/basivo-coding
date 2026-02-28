// ── Auth ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

// ── Projects ─────────────────────────────────────────────────────────────────

export interface Project {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  llm_base_url: string;
  llm_model: string | null;
  api_key_set: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreatePayload {
  name: string;
  description?: string;
  llm_base_url: string;
  llm_api_key: string;
  llm_model?: string;
}

// ── Files ─────────────────────────────────────────────────────────────────────

export interface FileNode {
  name: string;
  path: string;
  type: "file" | "directory";
  size?: number;
  language?: string;
  children?: FileNode[];
}

export interface OpenFile {
  path: string;
  content: string;
  language: string;
  dirty: boolean;
}

// ── WebSocket messages ───────────────────────────────────────────────────────

export type WsMessageType =
  | "connected"
  | "output"
  | "complete"
  | "error"
  | "status"
  | "ping";

export interface WsOutgoing {
  type: WsMessageType;
  data?: string;
  stream?: "stdout" | "stderr";
  exit_code?: number;
  message?: string;
}

export interface WsIncoming {
  type: "prompt" | "ping";
  content?: string;
}

// Terminal
export interface TerminalIncoming {
  type: "input" | "resize";
  data?: string;
  cols?: number;
  rows?: number;
}

export interface TerminalOutgoing {
  type: "output" | "exit" | "error";
  data?: string;
  code?: number;
  message?: string;
}

// ── LLM Providers ────────────────────────────────────────────────────────────

export interface TestConnectionPayload {
  base_url: string;
  api_key: string;
}

export interface TestConnectionResponse {
  success: boolean;
  models: string[];
  error?: string | null;
}

// ── Chat messages ─────────────────────────────────────────────────────────────

export type ChatRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: number;
  stream?: "stdout" | "stderr";
}

// ── Provider presets ──────────────────────────────────────────────────────────

export interface LLMProvider {
  label: string;
  baseUrl: string;
  defaultModel?: string;
  hint?: string;
}
