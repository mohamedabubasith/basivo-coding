import { api } from "./client";
import type { TestConnectionPayload, TestConnectionResponse, LLMProvider } from "@/types";

export const providersApi = {
  testConnection: (payload: TestConnectionPayload) =>
    api
      .post<TestConnectionResponse>("/providers/test-connection", payload)
      .then((r) => r.data),
};

export const LLM_PROVIDERS: LLMProvider[] = [
  {
    label: "OpenAI",
    baseUrl: "https://api.openai.com/v1",
    defaultModel: "gpt-4o",
    hint: "Get your API key from platform.openai.com",
  },
  {
    label: "Anthropic (Claude)",
    baseUrl: "https://api.anthropic.com/v1",
    defaultModel: "claude-sonnet-4-6",
    hint: "Get your API key from console.anthropic.com",
  },
  {
    label: "Groq",
    baseUrl: "https://api.groq.com/openai/v1",
    defaultModel: "llama-3.3-70b-versatile",
    hint: "Free tier available at console.groq.com",
  },
  {
    label: "Together AI",
    baseUrl: "https://api.together.xyz/v1",
    defaultModel: "meta-llama/Llama-3-70b-chat-hf",
    hint: "api.together.ai",
  },
  {
    label: "Fireworks AI",
    baseUrl: "https://api.fireworks.ai/inference/v1",
    defaultModel: "accounts/fireworks/models/llama-v3p3-70b-instruct",
    hint: "fireworks.ai",
  },
  {
    label: "Ollama (Local)",
    baseUrl: "http://localhost:11434/v1",
    defaultModel: "llama3.2",
    hint: "Requires Ollama running locally",
  },
  {
    label: "Custom / Other",
    baseUrl: "",
    hint: "Any OpenAI-compatible API endpoint",
  },
];
