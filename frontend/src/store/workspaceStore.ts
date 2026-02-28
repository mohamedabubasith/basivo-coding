import { create } from "zustand";
import type { FileNode, OpenFile, ChatMessage } from "@/types";

interface WorkspaceState {
  // File tree
  fileTree: FileNode | null;
  setFileTree: (tree: FileNode | null) => void;

  // Open editor tabs
  openFiles: OpenFile[];
  activeFilePath: string | null;
  openFile: (file: OpenFile) => void;
  closeFile: (path: string) => void;
  updateFileContent: (path: string, content: string) => void;
  markFileSaved: (path: string) => void;
  setActiveFile: (path: string) => void;

  // AI chat
  messages: ChatMessage[];
  addMessage: (msg: ChatMessage) => void;
  appendToLastMessage: (chunk: string) => void;
  clearMessages: () => void;
  isAiBusy: boolean;
  setAiBusy: (busy: boolean) => void;

  // Bottom panel
  bottomPanel: "terminal" | "preview";
  setBottomPanel: (p: "terminal" | "preview") => void;

  // Preview
  previewUrl: string | null;
  setPreviewUrl: (url: string | null) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  fileTree: null,
  setFileTree: (tree) => set({ fileTree: tree }),

  openFiles: [],
  activeFilePath: null,

  openFile: (file) =>
    set((s) => {
      const exists = s.openFiles.find((f) => f.path === file.path);
      if (exists) return { activeFilePath: file.path };
      return { openFiles: [...s.openFiles, file], activeFilePath: file.path };
    }),

  closeFile: (path) =>
    set((s) => {
      const next = s.openFiles.filter((f) => f.path !== path);
      const active =
        s.activeFilePath === path
          ? (next[next.length - 1]?.path ?? null)
          : s.activeFilePath;
      return { openFiles: next, activeFilePath: active };
    }),

  updateFileContent: (path, content) =>
    set((s) => ({
      openFiles: s.openFiles.map((f) =>
        f.path === path ? { ...f, content, dirty: true } : f
      ),
    })),

  markFileSaved: (path) =>
    set((s) => ({
      openFiles: s.openFiles.map((f) =>
        f.path === path ? { ...f, dirty: false } : f
      ),
    })),

  setActiveFile: (path) => set({ activeFilePath: path }),

  messages: [],
  addMessage: (msg) => set((s) => ({ messages: [...s.messages, msg] })),
  appendToLastMessage: (chunk) =>
    set((s) => {
      const msgs = [...s.messages];
      if (msgs.length === 0) return {};
      const last = msgs[msgs.length - 1];
      msgs[msgs.length - 1] = { ...last, content: last.content + chunk };
      return { messages: msgs };
    }),
  clearMessages: () => set({ messages: [] }),
  isAiBusy: false,
  setAiBusy: (busy) => set({ isAiBusy: busy }),

  bottomPanel: "terminal",
  setBottomPanel: (p) => set({ bottomPanel: p }),

  previewUrl: null,
  setPreviewUrl: (url) => set({ previewUrl: url }),
}));
