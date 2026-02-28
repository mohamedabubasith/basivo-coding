import { api } from "./client";
import type { TokenResponse, User } from "@/types";

export const authApi = {
  register: (email: string, password: string) =>
    api.post<User>("/auth/register", { email, password }).then((r) => r.data),

  login: (email: string, password: string) =>
    api.post<TokenResponse>("/auth/login", { email, password }).then((r) => r.data),

  me: () => api.get<User>("/auth/me").then((r) => r.data),

  forgotPassword: (email: string) =>
    api.post("/auth/forgot-password", { email }).then((r) => r.data),

  resetPassword: (token: string, new_password: string) =>
    api.post("/auth/reset-password", { token, new_password }).then((r) => r.data),
};
