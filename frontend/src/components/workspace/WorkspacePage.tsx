import { useEffect, useCallback, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import {
  ArrowLeft, Terminal as TerminalIcon, Globe, RefreshCw, Cpu, Key
} from "lucide-react";

import { projectsApi } from "@/api/projects";
import { filesApi } from "@/api/files";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { toast } from "@/components/ui/Toast";

import { FileExplorer } from "./FileExplorer";
import { CodeEditor } from "./CodeEditor";
import { AIChat } from "./AIChat";
import { TerminalPanel } from "./TerminalPanel";

export default function WorkspacePage() {
  const { projectId = "" } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const { bottomPanel, setBottomPanel, setFileTree, fileTree, openFile } =
    useWorkspaceStore();

  // ── Project metadata ──────────────────────────────────────────────────────

  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => projectsApi.get(projectId),
    retry: false,
  });

  // ── File tree ─────────────────────────────────────────────────────────────

  const [treeLoading, setTreeLoading] = useState(false);

  const refreshTree = useCallback(async () => {
    if (!projectId) return;
    setTreeLoading(true);
    try {
      const tree = await filesApi.tree(projectId);
      setFileTree(tree);
    } catch {
      toast.error("Failed to load file tree");
    } finally {
      setTreeLoading(false);
    }
  }, [projectId, setFileTree]);

  useEffect(() => {
    refreshTree();
  }, [refreshTree]);

  // ── Open a file in the editor ─────────────────────────────────────────────

  const handleFileClick = async (node: { path: string; type: string }) => {
    if (node.type !== "file") return;
    try {
      const { content, language, path } = await filesApi.read(projectId, node.path);
      openFile({ path, content, language, dirty: false });
    } catch {
      toast.error("Could not open file");
    }
  };

  // ── Resize state for panels ───────────────────────────────────────────────
  const [leftW, setLeftW] = useState(220);
  const [rightW, setRightW] = useState(320);
  const [bottomH, setBottomH] = useState(220);

  const startResize = (
    e: React.MouseEvent,
    which: "left" | "right" | "bottom"
  ) => {
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const startLeft = leftW;
    const startRight = rightW;
    const startBottom = bottomH;

    const onMove = (ev: MouseEvent) => {
      if (which === "left") setLeftW(Math.max(140, Math.min(400, startLeft + ev.clientX - startX)));
      if (which === "right") setRightW(Math.max(240, Math.min(500, startRight - ev.clientX + startX)));
      if (which === "bottom") setBottomH(Math.max(100, Math.min(500, startBottom - ev.clientY + startY)));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  if (projectLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-surface">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-surface gap-4">
        <p className="text-gray-400">Project not found</p>
        <Button onClick={() => navigate("/")} variant="outline">
          <ArrowLeft size={14} /> Back to Dashboard
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-surface overflow-hidden">
      {/* ── Top header ──────────────────────────────────────────────────── */}
      <header className="flex items-center gap-3 px-3 h-10 bg-surface-50 border-b border-gray-800 shrink-0">
        <button
          onClick={() => navigate("/")}
          className="text-gray-500 hover:text-gray-200 transition-colors"
        >
          <ArrowLeft size={15} />
        </button>
        <div className="h-4 w-px bg-gray-800" />
        <span className="text-sm font-medium text-gray-200 truncate max-w-[200px]">
          {project.name}
        </span>

        {/* Model info */}
        <div className="flex items-center gap-1.5 text-xs text-gray-600 ml-1">
          <Cpu size={11} />
          <span>{project.llm_model ?? "default"}</span>
        </div>
        {project.api_key_set && (
          <span className="text-xs text-success/70 flex items-center gap-1">
            <Key size={10} /> Key set
          </span>
        )}

        {/* Right actions */}
        <div className="ml-auto flex items-center gap-1">
          {treeLoading && <Spinner size="sm" />}
          <button
            onClick={refreshTree}
            className="text-gray-600 hover:text-gray-300 p-1.5 rounded transition-colors"
            title="Refresh files"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </header>

      {/* ── Main body ────────────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0">
        {/* Left: file explorer */}
        <div style={{ width: leftW }} className="shrink-0 flex flex-col min-h-0">
          <FileExplorer
            tree={fileTree}
            activePath={useWorkspaceStore.getState().activeFilePath}
            onFileClick={handleFileClick}
            onRefresh={refreshTree}
          />
        </div>

        {/* Drag handle: left */}
        <div
          className="panel-resize-handle shrink-0"
          onMouseDown={(e) => startResize(e, "left")}
        />

        {/* Center: editor + bottom panel */}
        <div className="flex-1 flex flex-col min-w-0 min-h-0">
          {/* Editor */}
          <div className="flex-1 flex min-h-0">
            <CodeEditor projectId={projectId} />
          </div>

          {/* Drag handle: bottom */}
          <div
            className="panel-resize-handle-h shrink-0"
            onMouseDown={(e) => startResize(e, "bottom")}
          />

          {/* Bottom panel: terminal / preview */}
          <div style={{ height: bottomH }} className="shrink-0 flex flex-col min-h-0 border-t border-gray-800">
            {/* Panel tabs */}
            <div className="flex items-center gap-1 px-2 py-1 bg-surface-50 border-b border-gray-800 shrink-0">
              <PanelTab
                icon={<TerminalIcon size={12} />}
                label="Terminal"
                active={bottomPanel === "terminal"}
                onClick={() => setBottomPanel("terminal")}
              />
              <PanelTab
                icon={<Globe size={12} />}
                label="Preview"
                active={bottomPanel === "preview"}
                onClick={() => setBottomPanel("preview")}
              />
            </div>
            <div className="flex-1 min-h-0">
              <div className={clsx("h-full", bottomPanel !== "terminal" && "hidden")}>
                <TerminalPanel projectId={projectId} active={bottomPanel === "terminal"} />
              </div>
              <div className={clsx("h-full flex flex-col items-center justify-center", bottomPanel !== "preview" && "hidden")}>
                <PreviewPanel projectId={projectId} />
              </div>
            </div>
          </div>
        </div>

        {/* Drag handle: right */}
        <div
          className="panel-resize-handle shrink-0"
          onMouseDown={(e) => startResize(e, "right")}
        />

        {/* Right: AI chat */}
        <div style={{ width: rightW }} className="shrink-0 flex flex-col min-h-0">
          <AIChat projectId={projectId} onFilesChanged={refreshTree} />
        </div>
      </div>
    </div>
  );
}

// ── Panel tab button ──────────────────────────────────────────────────────────

function PanelTab({
  icon, label, active, onClick,
}: { icon: React.ReactNode; label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors",
        active ? "bg-surface-200 text-white" : "text-gray-500 hover:text-gray-300"
      )}
    >
      {icon} {label}
    </button>
  );
}

// ── Preview panel ─────────────────────────────────────────────────────────────

function PreviewPanel({ projectId }: { projectId: string }) {
  const { previewUrl, setPreviewUrl } = useWorkspaceStore();
  const [customUrl, setCustomUrl] = useState("http://localhost:5173");

  const load = () => setPreviewUrl(customUrl.trim());

  if (previewUrl) {
    return (
      <div className="flex flex-col w-full h-full">
        <div className="flex items-center gap-2 px-3 py-1.5 bg-surface-50 border-b border-gray-800 shrink-0">
          <input
            value={customUrl}
            onChange={(e) => setCustomUrl(e.target.value)}
            className="flex-1 bg-surface-200 border border-gray-700 rounded px-2 py-1 text-xs text-gray-300"
          />
          <button onClick={load} className="text-xs text-brand-400 hover:text-white transition-colors">
            Go
          </button>
          <button onClick={() => setPreviewUrl(null)} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
            Close
          </button>
        </div>
        <iframe src={previewUrl} className="flex-1 bg-white" title="Preview" />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-3 text-center px-6">
      <Globe size={32} className="text-gray-700" />
      <div>
        <p className="text-sm text-gray-400">Live Preview</p>
        <p className="text-xs text-gray-600 mt-1">
          Run your dev server (e.g. <code className="bg-surface-200 px-1 rounded">npm run dev</code>) in the terminal, then load the URL here.
        </p>
      </div>
      <div className="flex gap-2 w-full max-w-xs">
        <input
          value={customUrl}
          onChange={(e) => setCustomUrl(e.target.value)}
          placeholder="http://localhost:5173"
          className="flex-1 bg-surface-200 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-gray-300 focus:outline-none focus:ring-1 focus:ring-brand/50"
        />
        <button
          onClick={load}
          className="bg-brand text-white text-xs px-3 py-1.5 rounded-lg hover:bg-brand-600 transition-colors"
        >
          Load
        </button>
      </div>
    </div>
  );
}
