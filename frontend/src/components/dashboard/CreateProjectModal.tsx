import { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Wifi, WifiOff, ChevronDown, Loader2, Eye, EyeOff, Plus
} from "lucide-react";

import { providersApi, LLM_PROVIDERS } from "@/api/providers";
import { projectsApi } from "@/api/projects";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/components/ui/Toast";
import { apiErrorMessage } from "@/api/client";
import type { Project } from "@/types";

// ── Schema ────────────────────────────────────────────────────────────────────

const schema = z.object({
  name: z.string().min(1, "Project name is required").max(255),
  description: z.string().max(2000).optional(),
  llm_base_url: z.string().url("Enter a valid URL (include https://)"),
  llm_api_key: z.string().min(1, "API key is required"),
  llm_model: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

// ── Props ─────────────────────────────────────────────────────────────────────

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (project: Project) => void;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function CreateProjectModal({ open, onClose, onCreated }: Props) {
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"idle" | "ok" | "fail">("idle");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedProvider, setSelectedProvider] = useState(0);

  const {
    register,
    handleSubmit,
    control,
    setValue,
    watch,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const baseUrl = watch("llm_base_url");
  const apiKey = watch("llm_api_key");

  // ── Provider preset selector ──────────────────────────────────────────────

  const handleProviderSelect = (index: number) => {
    const provider = LLM_PROVIDERS[index];
    setSelectedProvider(index);
    setValue("llm_base_url", provider.baseUrl, { shouldValidate: false });
    if (provider.defaultModel) {
      setValue("llm_model", provider.defaultModel);
    }
    setConnectionStatus("idle");
    setAvailableModels([]);
  };

  // ── Test connection ────────────────────────────────────────────────────────

  const handleTestConnection = async () => {
    if (!baseUrl || !apiKey) {
      toast.warning("Fill in Base URL and API Key first");
      return;
    }
    setTesting(true);
    setConnectionStatus("idle");
    try {
      const res = await providersApi.testConnection({ base_url: baseUrl, api_key: apiKey });
      if (res.success) {
        setConnectionStatus("ok");
        setAvailableModels(res.models);
        toast.success(
          "Connection successful!",
          res.models.length
            ? `Found ${res.models.length} models`
            : res.error ?? "Connected, enter model name manually"
        );
      } else {
        setConnectionStatus("fail");
        toast.error("Connection failed", res.error ?? "Unknown error");
      }
    } catch (err) {
      setConnectionStatus("fail");
      toast.error("Connection failed", apiErrorMessage(err));
    } finally {
      setTesting(false);
    }
  };

  // ── Submit ────────────────────────────────────────────────────────────────

  const onSubmit = handleSubmit(async (data) => {
    try {
      const project = await projectsApi.create(data);
      toast.success("Project created!", project.name);
      reset();
      setConnectionStatus("idle");
      setAvailableModels([]);
      onCreated(project);
      onClose();
    } catch (err) {
      toast.error("Failed to create project", apiErrorMessage(err));
    }
  });

  const handleClose = () => {
    reset();
    setConnectionStatus("idle");
    setAvailableModels([]);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="New Project"
      subtitle="Set up your AI coding workspace"
      size="xl"
    >
      <form onSubmit={onSubmit} className="flex flex-col gap-5">
        {/* ── Project info ──────────────────────────────────────────────── */}
        <section className="flex flex-col gap-3">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Project
          </h3>
          <Input
            label="Project name"
            placeholder="My Vite React App"
            error={errors.name?.message}
            {...register("name")}
          />
          <Input
            label="Description (optional)"
            placeholder="Short description…"
            error={errors.description?.message}
            {...register("description")}
          />
        </section>

        {/* ── LLM Provider ──────────────────────────────────────────────── */}
        <section className="flex flex-col gap-3">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
            AI Provider (BYOK)
          </h3>

          {/* Provider quick-select */}
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {LLM_PROVIDERS.map((p, i) => (
              <button
                key={p.label}
                type="button"
                onClick={() => handleProviderSelect(i)}
                className={`text-xs px-3 py-2 rounded-lg border transition-all text-left ${
                  selectedProvider === i
                    ? "border-brand bg-brand/10 text-white"
                    : "border-gray-700 text-gray-400 hover:border-gray-500 hover:text-gray-200"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {LLM_PROVIDERS[selectedProvider]?.hint && (
            <p className="text-xs text-gray-500">
              💡 {LLM_PROVIDERS[selectedProvider].hint}
            </p>
          )}

          <Input
            label="Base URL"
            placeholder="https://api.openai.com/v1"
            error={errors.llm_base_url?.message}
            {...register("llm_base_url")}
          />

          {/* API Key + test connection */}
          <div className="flex flex-col gap-1">
            <Input
              label="API Key"
              type={showKey ? "text" : "password"}
              placeholder="sk-…"
              error={errors.llm_api_key?.message}
              rightSlot={
                <button
                  type="button"
                  onClick={() => setShowKey((v) => !v)}
                  className="text-gray-500 hover:text-gray-300 p-1 transition-colors"
                >
                  {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              }
              {...register("llm_api_key")}
            />
            <button
              type="button"
              onClick={handleTestConnection}
              disabled={testing}
              className="self-start flex items-center gap-1.5 text-xs text-gray-400 hover:text-brand-400 transition-colors mt-1 disabled:opacity-50"
            >
              {testing ? (
                <Loader2 size={12} className="animate-spin" />
              ) : connectionStatus === "ok" ? (
                <Wifi size={12} className="text-success" />
              ) : connectionStatus === "fail" ? (
                <WifiOff size={12} className="text-danger" />
              ) : (
                <Wifi size={12} />
              )}
              {testing
                ? "Testing connection…"
                : connectionStatus === "ok"
                ? "Connected ✓ — test again"
                : connectionStatus === "fail"
                ? "Failed — retry"
                : "Test connection & fetch models"}
            </button>
          </div>

          {/* Model selector */}
          <div className="flex flex-col gap-1">
            <label className="text-sm font-medium text-gray-300">Model</label>
            {availableModels.length > 0 ? (
              <Controller
                control={control}
                name="llm_model"
                render={({ field }) => (
                  <div className="relative">
                    <select
                      {...field}
                      className="w-full appearance-none bg-surface-200 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-brand/60"
                    >
                      <option value="">Select a model…</option>
                      {availableModels.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                    <ChevronDown
                      size={14}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
                    />
                  </div>
                )}
              />
            ) : (
              <Input
                placeholder={LLM_PROVIDERS[selectedProvider]?.defaultModel ?? "gpt-4o"}
                hint={
                  connectionStatus === "idle"
                    ? "Test connection to load available models, or type one manually"
                    : undefined
                }
                error={errors.llm_model?.message}
                {...register("llm_model")}
              />
            )}
          </div>
        </section>

        {/* ── Actions ─────────────────────────────────────────────────────── */}
        <div className="flex justify-end gap-3 pt-2 border-t border-gray-700/50">
          <Button type="button" variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="submit" loading={isSubmitting}>
            <Plus size={15} /> Create Project
          </Button>
        </div>
      </form>
    </Modal>
  );
}
