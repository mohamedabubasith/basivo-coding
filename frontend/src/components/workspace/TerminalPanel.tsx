import { useEffect, useRef, useCallback } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";

import { wsUrl } from "@/api/client";

interface Props {
  projectId: string;
  active: boolean;
}

export function TerminalPanel({ projectId, active }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<XTerm | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitRef = useRef<FitAddon | null>(null);

  const connect = useCallback(() => {
    if (!xtermRef.current) return;
    const ws = new WebSocket(wsUrl(`/projects/${projectId}/terminal`));
    wsRef.current = ws;

    ws.onopen = () => xtermRef.current?.write("\r\n\x1b[32m● Connected\x1b[0m\r\n\r\n");
    ws.onclose = () => xtermRef.current?.write("\r\n\x1b[31m● Disconnected\x1b[0m\r\n");
    ws.onerror = () => xtermRef.current?.write("\r\n\x1b[31m● Connection error\x1b[0m\r\n");

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data) as { type: string; data?: string; code?: number };
        if (msg.type === "output" && msg.data) {
          xtermRef.current?.write(msg.data);
        } else if (msg.type === "exit") {
          xtermRef.current?.write(`\r\n\x1b[33m● Shell exited (code ${msg.code ?? 0})\x1b[0m\r\n`);
        }
      } catch {
        // binary fallback
        xtermRef.current?.write(evt.data);
      }
    };
  }, [projectId]);

  // ── Initialise xterm ─────────────────────────────────────────────────────

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new XTerm({
      theme: {
        background: "#0f1117",
        foreground: "#e5e7eb",
        cursor: "#6366f1",
        black: "#1e2130",
        red: "#ef4444",
        green: "#22c55e",
        yellow: "#f59e0b",
        blue: "#6366f1",
        magenta: "#a855f7",
        cyan: "#06b6d4",
        white: "#e5e7eb",
        brightBlack: "#374151",
        brightRed: "#f87171",
        brightGreen: "#4ade80",
        brightYellow: "#fbbf24",
        brightBlue: "#818cf8",
        brightMagenta: "#c084fc",
        brightCyan: "#22d3ee",
        brightWhite: "#f9fafb",
      },
      fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
      fontSize: 13,
      lineHeight: 1.5,
      cursorBlink: true,
      cursorStyle: "bar",
      scrollback: 5000,
      allowProposedApi: true,
    });

    const fit = new FitAddon();
    const links = new WebLinksAddon();
    term.loadAddon(fit);
    term.loadAddon(links);
    term.open(containerRef.current);
    fit.fit();

    xtermRef.current = term;
    fitRef.current = fit;

    // Forward keyboard input to backend
    term.onData((data) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "input", data }));
      }
    });

    // Forward resize events
    term.onResize(({ cols, rows }) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "resize", cols, rows }));
      }
    });

    connect();

    // Resize observer
    const ro = new ResizeObserver(() => fit.fit());
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      wsRef.current?.close();
      term.dispose();
    };
  }, [connect]);

  // Refit when panel becomes visible
  useEffect(() => {
    if (active) {
      setTimeout(() => fitRef.current?.fit(), 50);
    }
  }, [active]);

  return (
    <div className="flex flex-col h-full bg-[#0f1117]">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-3 py-1.5 border-b border-gray-800 bg-surface-50 shrink-0">
        <span className="text-xs font-semibold text-gray-400">Terminal</span>
        <button
          onClick={() => { wsRef.current?.close(); connect(); }}
          className="text-xs text-gray-600 hover:text-gray-300 transition-colors ml-auto"
        >
          Restart
        </button>
        <button
          onClick={() => xtermRef.current?.clear()}
          className="text-xs text-gray-600 hover:text-gray-300 transition-colors"
        >
          Clear
        </button>
      </div>

      {/* xterm container */}
      <div ref={containerRef} className="flex-1 min-h-0 p-2" />
    </div>
  );
}
