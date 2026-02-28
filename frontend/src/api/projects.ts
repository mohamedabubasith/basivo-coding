import { api } from "./client";
import type { Project, ProjectCreatePayload } from "@/types";

export const projectsApi = {
  list: () =>
    api.get<{ projects: Project[]; total: number }>("/projects").then((r) => r.data),

  get: (id: string) => api.get<Project>(`/projects/${id}`).then((r) => r.data),

  create: (payload: ProjectCreatePayload) =>
    api.post<Project>("/projects", payload).then((r) => r.data),

  delete: (id: string) => api.delete(`/projects/${id}`),
};
