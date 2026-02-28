import { api } from "./client";
import type { FileNode } from "@/types";

export const filesApi = {
  tree: (projectId: string) =>
    api.get<FileNode>(`/projects/${projectId}/files`).then((r) => r.data),

  read: (projectId: string, path: string) =>
    api
      .get<{ path: string; content: string; language: string }>(
        `/projects/${projectId}/files/content`,
        { params: { path } }
      )
      .then((r) => r.data),

  write: (projectId: string, path: string, content: string) =>
    api
      .put<{ path: string; saved: boolean }>(
        `/projects/${projectId}/files/content`,
        { path, content }
      )
      .then((r) => r.data),

  delete: (projectId: string, path: string) =>
    api
      .delete<{ path: string; deleted: boolean }>(
        `/projects/${projectId}/files`,
        { params: { path } }
      )
      .then((r) => r.data),
};
