import { useState, useEffect, useRef, useCallback } from "react";
import { Send, Bot, User, AlertCircle, CheckCircle2, Loader2, Trash2 } from "lucide-react";
import { clsx } from "clsx";

import { wsUrl } from "@/api/client";
import { useWorkspaceStore } from "@/store/workspaceStore";
import type { WsOutgoing, ChatMessage } from "@/types";

let _msgId = 0;
const uid = () => String(++_msgId);

interface Props {
  projectId: string;
  onFilesChanged?: () => void;
}

export function AIChat({ projectId, onFilesChanged }: Props) {
  const [input, setInput] = useState("");
  const [wsState, setWsState] = useState<"connecting" | "open" | "closed" | "error">("closed");
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const { messages, addMessage, appendToLastMessage, clearMessages, isAiBusy, setAiBusy } =
    useWorkspaceStore();

  // ── WebSocket lifecycle ───────────────────────────────────────────────────

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setWsState("connecting");

    const ws = new WebSocket(wsUrl(`/ws/${projectId}`));
    wsRef.current = ws;

    ws.onopen = () => setWsState("open");
    ws.onclose = () => { setWsState("closed"); setAiBusy(false); };
    ws.onerror = () => { setWsState("error"); setAiBusy(false); };

    ws.onmessage = (evt) => {
      try {
        const msg: WsOutgoing = JSON.parse(evt.data);
        handleWsMessage(msg);
      } catch {
        /* ignore malformed */
      }
    };
  }, [projectId]);

  useEffect(() => {
    connect();
    // Keepalive ping every 25 seconds
    const ping = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 25_000);

    return () => {
      clearInterval(ping);
      wsRef.current?.close();
    };
  }, [connect]);

  // Scroll to bottom on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Message handler ───────────────────────────────────────────────────────

  const currentAssistantId = useRef<string | null>(null);

  const handleWsMessage = (msg: WsOutgoing) => {
    switch (msg.type) {
      case "connected":
        addMessage({ id: uid(), role: "system", content: msg.message ?? "Connected", timestamp: Date.now() });
        break;

      case "status":
        if (msg.message === "pong") break;
        addMessage({ id: uid(), role: "system", content: `⚙ ${msg.message}`, timestamp: Date.now() });
        break;

      case "output": {
        const chunk = msg.data ?? "";
        if (!chunk) break;
        // Stream into current assistant message or create one
        if (!currentAssistantId.current) {
          const id = uid();
          currentAssistantId.current = id;
          addMessage({
            id,
            role: "assistant",
            content: chunk,
            stream: msg.stream,
            timestamp: Date.now(),
          });
        } else {
          appendToLastMessage(chunk + "\n");
        }
        break;
      }

      case "complete":
        setAiBusy(false);
        currentAssistantId.current = null;
        addMessage({
          id: uid(),
          role: "system",
          content: msg.exit_code === 0 ? "✓ Done" : `⚠ Exited with code ${msg.exit_code}`,
          timestamp: Date.now(),
        });
        onFilesChanged?.();
        break;

      case "error":
        setAiBusy(false);
        currentAssistantId.current = null;
        addMessage({ id: uid(), role: "system", content: `✗ ${msg.message}`, timestamp: Date.now() });
        break;
    }
  };

  // ── Send prompt ───────────────────────────────────────────────────────────

  const sendPrompt = () => {
    const text = input.trim();
    if (!text || isAiBusy || wsRef.current?.readyState !== WebSocket.OPEN) return;

    addMessage({ id: uid(), role: "user", content: text, timestamp: Date.now() });
    currentAssistantId.current = null;
    setAiBusy(true);
    setInput("");

    wsRef.current.send(JSON.stringify({ type: "prompt", content: text }));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPrompt();
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full bg-surface-50 border-l border-gray-800">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-800 shrink-0">
        <div className="flex items-center gap-2">
          <Bot size={15} className="text-brand-400" />
          <span className="text-xs font-semibold text-gray-300">AI Chat</span>
        </div>
        <div className="flex items-center gap-2">
          <StatusDot state={wsState} />
          {wsState === "closed" || wsState === "error" ? (
            <button onClick={connect} className="text-xs text-gray-500 hover:text-brand-400 transition-colors">
              Reconnect
            </button>
          ) : null}
          <button
            onClick={clearMessages}
            className="text-gray-600 hover:text-gray-300 transition-colors p-1"
            title="Clear chat"
          >
            <Trash2 size={12} />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 py-3 flex flex-col gap-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center gap-3">
            <Bot size={36} className="text-gray-700" />
            <div>
              <p className="text-sm text-gray-400">Ask AI to build something</p>
              <p className="text-xs text-gray-600 mt-1">
                e.g. "Create a React todo app with Tailwind"
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} msg={msg} />
        ))}

        {isAiBusy && (
          <div className="flex items-center gap-2 text-xs text-gray-500 ml-1">
            <Loader2 size={12} className="animate-spin text-brand-400" />
            <span className="animate-pulse">AI is working…</span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 p-3 shrink-0">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              wsState !== "open"
                ? "Connecting…"
                : isAiBusy
                ? "AI is working…"
                : "Describe what you want to build… (Enter to send)"
            }
            disabled={wsState !== "open" || isAiBusy}
            rows={3}
            className={clsx(
              "w-full bg-surface-200 border border-gray-700 rounded-xl text-sm text-gray-100",
              "placeholder-gray-600 resize-none px-3 py-2.5 pr-10",
              "focus:outline-none focus:ring-2 focus:ring-brand/50 focus:border-gray-600 transition-all",
              "disabled:opacity-50"
            )}
          />
          <button
            onClick={sendPrompt}
            disabled={!input.trim() || isAiBusy || wsState !== "open"}
            className={clsx(
              "absolute right-2 bottom-2 p-1.5 rounded-lg transition-all",
              input.trim() && !isAiBusy && wsState === "open"
                ? "bg-brand text-white hover:bg-brand-600"
                : "text-gray-600 cursor-not-allowed"
            )}
          >
            <Send size={14} />
          </button>
        </div>
        <p className="text-xs text-gray-700 mt-1.5">
          Shift+Enter for new line · Enter to send
        </p>
      </div>
    </div>
  );
}

// ── Message bubble ────────────────────────────────────────────────────────────

function MessageBubble({ msg }: { msg: ChatMessage }) {
  if (msg.role === "system") {
    const isOk = msg.content.startsWith("✓");
    const isErr = msg.content.startsWith("✗");
    return (
      <div className={clsx(
        "flex items-center gap-1.5 text-xs py-1 px-2 rounded-lg",
        isOk ? "text-success bg-success/5" : isErr ? "text-danger bg-danger/5" : "text-gray-500"
      )}>
        {isOk ? <CheckCircle2 size={11} /> : isErr ? <AlertCircle size={11} /> : null}
        <span>{msg.content}</span>
      </div>
    );
  }

  if (msg.role === "user") {
    return (
      <div className="flex gap-2 justify-end">
        <div className="msg-user max-w-[90%]">
          <p className="whitespace-pre-wrap break-words">{msg.content}</p>
        </div>
        <div className="w-6 h-6 rounded-full bg-brand/20 flex items-center justify-center shrink-0 mt-0.5">
          <User size={12} className="text-brand-400" />
        </div>
      </div>
    );
  }

  // assistant
  return (
    <div className="flex gap-2">
      <div className="w-6 h-6 rounded-full bg-surface-200 flex items-center justify-center shrink-0 mt-0.5">
        <Bot size={12} className="text-gray-400" />
      </div>
      <div className="msg-ai max-w-[90%] flex-1">
        <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-gray-300">
          {msg.content}
        </pre>
      </div>
    </div>
  );
}

// ── Connection status dot ─────────────────────────────────────────────────────

function StatusDot({ state }: { state: string }) {
  const colors = {
    open: "bg-success",
    connecting: "bg-warning animate-pulse",
    closed: "bg-gray-600",
    error: "bg-danger",
  }[state] ?? "bg-gray-600";

  return (
    <span className={clsx("w-1.5 h-1.5 rounded-full shrink-0", colors)} />
  );
}
