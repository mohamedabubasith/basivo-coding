import { useState } from "react";
import {
  ChevronRight, ChevronDown, File, Folder, FolderOpen,
  RefreshCw, FileCode, FileText, Image
} from "lucide-react";
import { clsx } from "clsx";
import type { FileNode } from "@/types";

interface Props {
  tree: FileNode | null;
  activePath: string | null;
  onFileClick: (node: FileNode) => void;
  onRefresh: () => void;
}

export function FileExplorer({ tree, activePath, onFileClick, onRefresh }: Props) {
  return (
    <div className="flex flex-col h-full bg-surface-50 border-r border-gray-800">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Explorer
        </span>
        <button
          onClick={onRefresh}
          className="text-gray-600 hover:text-gray-300 p-1 rounded transition-colors"
          title="Refresh"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Tree */}
      <div className="flex-1 overflow-y-auto py-1">
        {!tree || (tree.children ?? []).length === 0 ? (
          <div className="px-3 py-6 text-center">
            <p className="text-xs text-gray-600">
              No files yet. Ask AI to create your project!
            </p>
          </div>
        ) : (
          (tree.children ?? []).map((node) => (
            <TreeNode
              key={node.path}
              node={node}
              depth={0}
              activePath={activePath}
              onFileClick={onFileClick}
            />
          ))
        )}
      </div>
    </div>
  );
}

// ── Tree node (recursive) ─────────────────────────────────────────────────────

function TreeNode({
  node,
  depth,
  activePath,
  onFileClick,
}: {
  node: FileNode;
  depth: number;
  activePath: string | null;
  onFileClick: (n: FileNode) => void;
}) {
  const [open, setOpen] = useState(depth === 0);

  if (node.type === "directory") {
    return (
      <div>
        <div
          className="file-row"
          style={{ paddingLeft: `${8 + depth * 12}px` }}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="text-gray-500 shrink-0">
            {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          </span>
          <span className="text-yellow-500/80 shrink-0">
            {open ? <FolderOpen size={14} /> : <Folder size={14} />}
          </span>
          <span className="truncate text-gray-300">{node.name}</span>
        </div>
        {open && node.children?.map((child) => (
          <TreeNode
            key={child.path}
            node={child}
            depth={depth + 1}
            activePath={activePath}
            onFileClick={onFileClick}
          />
        ))}
      </div>
    );
  }

  const isActive = activePath === node.path;
  return (
    <div
      className={clsx("file-row", isActive && "active")}
      style={{ paddingLeft: `${8 + depth * 12 + 16}px` }}
      onClick={() => onFileClick(node)}
    >
      <FileIcon name={node.name} />
      <span className={clsx("truncate", isActive ? "text-white" : "text-gray-400")}>
        {node.name}
      </span>
    </div>
  );
}

// ── File icon by extension ────────────────────────────────────────────────────

function FileIcon({ name }: { name: string }) {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  const classes = "shrink-0";

  if (["ts", "tsx"].includes(ext)) return <FileCode size={14} className={clsx(classes, "text-blue-400")} />;
  if (["js", "jsx"].includes(ext)) return <FileCode size={14} className={clsx(classes, "text-yellow-400")} />;
  if (["py"].includes(ext)) return <FileCode size={14} className={clsx(classes, "text-green-400")} />;
  if (["css", "scss", "sass"].includes(ext)) return <FileCode size={14} className={clsx(classes, "text-pink-400")} />;
  if (["html", "htm"].includes(ext)) return <FileCode size={14} className={clsx(classes, "text-orange-400")} />;
  if (["json", "yaml", "yml", "toml"].includes(ext)) return <FileCode size={14} className={clsx(classes, "text-gray-400")} />;
  if (["md", "mdx"].includes(ext)) return <FileText size={14} className={clsx(classes, "text-gray-400")} />;
  if (["png", "jpg", "jpeg", "gif", "svg", "webp"].includes(ext)) return <Image size={14} className={clsx(classes, "text-purple-400")} />;
  return <File size={14} className={clsx(classes, "text-gray-500")} />;
}
