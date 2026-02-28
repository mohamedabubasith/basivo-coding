import { useRef } from "react";
import MonacoEditor from "@monaco-editor/react";
import { X, Save, Circle } from "lucide-react";
import { clsx } from "clsx";
import { filesApi } from "@/api/files";
import { useWorkspaceStore } from "@/store/workspaceStore";
import { toast } from "@/components/ui/Toast";
import type { OpenFile } from "@/types";

interface Props {
  projectId: string;
}

export function CodeEditor({ projectId }: Props) {
  const { openFiles, activeFilePath, setActiveFile, closeFile, updateFileContent, markFileSaved } =
    useWorkspaceStore();
  const editorRef = useRef<unknown>(null);

  const activeFile = openFiles.find((f) => f.path === activeFilePath);

  const handleSave = async (file: OpenFile) => {
    try {
      await filesApi.write(projectId, file.path, file.content);
      markFileSaved(file.path);
      toast.success("Saved", file.path);
    } catch {
      toast.error("Failed to save file");
    }
  };

  // Ctrl/Cmd+S to save
  const handleEditorMount = (editor: unknown) => {
    editorRef.current = editor;
    const e = editor as { addCommand: (k: number, fn: () => void) => void; KeyMod: { CtrlCmd: number }; KeyCode: { KeyS: number } };
    // Monaco keybinding
    import("monaco-editor").then((monaco) => {
      (editor as { addCommand: (k: number, fn: () => void) => void }).addCommand(
        monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS,
        () => {
          const f = useWorkspaceStore.getState().openFiles.find(
            (f) => f.path === useWorkspaceStore.getState().activeFilePath
          );
          if (f) handleSave(f);
        }
      );
    }).catch(() => {});
  };

  if (openFiles.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center bg-surface-50 gap-3">
        <div className="w-16 h-16 rounded-2xl bg-surface-200 flex items-center justify-center">
          <svg className="w-8 h-8 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
          </svg>
        </div>
        <div>
          <p className="text-gray-400 font-medium text-sm">No file open</p>
          <p className="text-gray-600 text-xs mt-1">Click a file in the explorer or ask AI to create one</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Tabs */}
      <div className="flex items-center bg-surface-50 border-b border-gray-800 overflow-x-auto">
        {openFiles.map((f) => (
          <div
            key={f.path}
            onClick={() => setActiveFile(f.path)}
            className={clsx(
              "flex items-center gap-2 px-3 py-2 text-xs border-r border-gray-800 cursor-pointer",
              "shrink-0 max-w-[180px] transition-colors",
              f.path === activeFilePath
                ? "bg-surface text-white border-b-2 border-b-brand"
                : "text-gray-500 hover:text-gray-300 hover:bg-surface-200"
            )}
          >
            {f.dirty ? (
              <Circle size={7} className="text-brand fill-brand shrink-0" />
            ) : null}
            <span className="truncate">{f.path.split("/").pop()}</span>
            <button
              onClick={(e) => { e.stopPropagation(); closeFile(f.path); }}
              className="text-gray-600 hover:text-gray-300 transition-colors shrink-0 ml-auto"
            >
              <X size={12} />
            </button>
          </div>
        ))}

        {/* Save button */}
        {activeFile?.dirty && (
          <button
            onClick={() => activeFile && handleSave(activeFile)}
            className="ml-auto mr-2 flex items-center gap-1 text-xs text-gray-500 hover:text-white transition-colors px-2 py-1"
          >
            <Save size={12} /> Save
          </button>
        )}
      </div>

      {/* Editor */}
      {activeFile && (
        <div className="flex-1 min-h-0">
          <MonacoEditor
            height="100%"
            language={activeFile.language}
            value={activeFile.content}
            theme="vs-dark"
            onMount={handleEditorMount}
            onChange={(val) => {
              if (val !== undefined) updateFileContent(activeFile.path, val);
            }}
            options={{
              fontSize: 13,
              fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
              fontLigatures: true,
              lineHeight: 1.7,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              wordWrap: "on",
              tabSize: 2,
              renderWhitespace: "selection",
              smoothScrolling: true,
              cursorBlinking: "smooth",
              padding: { top: 12, bottom: 12 },
              scrollbar: { verticalScrollbarSize: 6, horizontalScrollbarSize: 6 },
              renderLineHighlight: "gutter",
              suggest: { showFiles: false },
            }}
          />
        </div>
      )}
    </div>
  );
}
