import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Code2, Plus, Trash2, LogOut, Clock, Key, ExternalLink,
  FolderOpen, Cpu
} from "lucide-react";

import { projectsApi } from "@/api/projects";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import { toast } from "@/components/ui/Toast";
import { CreateProjectModal } from "./CreateProjectModal";
import type { Project } from "@/types";

export default function Dashboard() {
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();
  const { user, clearAuth } = useAuthStore();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list(),
  });

  const handleDelete = async (id: string, name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
    try {
      await projectsApi.delete(id);
      qc.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project deleted");
    } catch {
      toast.error("Failed to delete project");
    }
  };

  const handleLogout = () => {
    clearAuth();
    navigate("/auth");
  };

  return (
    <div className="min-h-screen bg-surface">
      {/* Header */}
      <header className="border-b border-gray-800 bg-surface-50/50 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-brand/20 border border-brand/30 flex items-center justify-center">
              <Code2 size={15} className="text-brand-400" />
            </div>
            <span className="font-semibold text-white text-sm">Basivo</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500">{user?.email}</span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              <LogOut size={14} /> Sign out
            </Button>
          </div>
        </div>
      </header>

      {/* Body */}
      <main className="max-w-6xl mx-auto px-6 py-10">
        {/* Hero row */}
        <div className="flex items-end justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-white">Projects</h1>
            <p className="text-sm text-gray-400 mt-1">
              Each project gets an isolated AI workspace with your own API key.
            </p>
          </div>
          <Button onClick={() => setCreating(true)}>
            <Plus size={16} /> New Project
          </Button>
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="flex justify-center py-20">
            <Spinner size="lg" />
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !data?.projects.length && (
          <div className="text-center py-20 border border-dashed border-gray-700 rounded-2xl">
            <FolderOpen size={40} className="text-gray-600 mx-auto mb-3" />
            <p className="text-gray-400 font-medium">No projects yet</p>
            <p className="text-gray-600 text-sm mt-1 mb-5">
              Create your first project to start coding with AI
            </p>
            <Button onClick={() => setCreating(true)}>
              <Plus size={15} /> Create Project
            </Button>
          </div>
        )}

        {/* Project grid */}
        {!!data?.projects.length && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.projects.map((p) => (
              <ProjectCard
                key={p.id}
                project={p}
                onOpen={() => navigate(`/workspace/${p.id}`)}
                onDelete={(e) => handleDelete(p.id, p.name, e)}
              />
            ))}
          </div>
        )}
      </main>

      <CreateProjectModal
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={() => {
          qc.invalidateQueries({ queryKey: ["projects"] });
          setCreating(false);
        }}
      />
    </div>
  );
}

// ── Project Card ─────────────────────────────────────────────────────────────

function ProjectCard({
  project,
  onOpen,
  onDelete,
}: {
  project: Project;
  onOpen: () => void;
  onDelete: (e: React.MouseEvent) => void;
}) {
  const timeAgo = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  const providerHost = (() => {
    try {
      return new URL(project.llm_base_url).hostname.replace("www.", "");
    } catch {
      return project.llm_base_url;
    }
  })();

  return (
    <div
      onClick={onOpen}
      className="group relative bg-surface-50 border border-gray-700/60 rounded-2xl p-5
                 hover:border-gray-600 hover:shadow-lg hover:shadow-brand/5 transition-all
                 cursor-pointer"
    >
      {/* Top row */}
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 rounded-xl bg-brand/10 border border-brand/20 flex items-center justify-center">
          <Code2 size={17} className="text-brand-400" />
        </div>
        <button
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-danger p-1.5 rounded-lg hover:bg-danger/10 transition-all"
        >
          <Trash2 size={14} />
        </button>
      </div>

      {/* Name */}
      <h3 className="font-semibold text-white text-sm mb-1 truncate">{project.name}</h3>
      {project.description && (
        <p className="text-xs text-gray-500 mb-3 line-clamp-2">{project.description}</p>
      )}

      {/* Meta pills */}
      <div className="flex flex-wrap gap-1.5 mb-4">
        <span className="inline-flex items-center gap-1 text-xs bg-surface-200 text-gray-400 px-2 py-0.5 rounded-full">
          <Cpu size={10} /> {project.llm_model ?? "auto"}
        </span>
        <span className="inline-flex items-center gap-1 text-xs bg-surface-200 text-gray-400 px-2 py-0.5 rounded-full">
          <ExternalLink size={10} /> {providerHost}
        </span>
        {project.api_key_set && (
          <span className="inline-flex items-center gap-1 text-xs bg-success/10 text-success px-2 py-0.5 rounded-full">
            <Key size={10} /> Key set
          </span>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <span className="inline-flex items-center gap-1 text-xs text-gray-600">
          <Clock size={10} /> {timeAgo(project.updated_at)}
        </span>
        <span className="text-xs text-brand-400 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
          Open workspace <ExternalLink size={10} />
        </span>
      </div>
    </div>
  );
}
