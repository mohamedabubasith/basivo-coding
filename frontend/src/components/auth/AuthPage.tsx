import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff, Code2, Lock, Mail, ArrowRight } from "lucide-react";

import { authApi } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { toast } from "@/components/ui/Toast";
import { apiErrorMessage } from "@/api/client";

// ── Validation schemas ────────────────────────────────────────────────────────

const passwordRules = z
  .string()
  .min(8, "At least 8 characters")
  .regex(/[A-Z]/, "Must contain an uppercase letter")
  .regex(/[a-z]/, "Must contain a lowercase letter")
  .regex(/[0-9]/, "Must contain a digit");

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

const registerSchema = z
  .object({
    email: z.string().email("Enter a valid email address"),
    password: passwordRules,
    confirmPassword: z.string(),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type LoginForm = z.infer<typeof loginSchema>;
type RegisterForm = z.infer<typeof registerSchema>;

// ── Component ─────────────────────────────────────────────────────────────────

export default function AuthPage() {
  const [mode, setMode] = useState<"login" | "register" | "forgot">("login");
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  // ── Login form ───────────────────────────────────────────────────────────
  const loginForm = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });
  const registerForm = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) });
  const forgotForm = useForm<{ email: string }>({
    resolver: zodResolver(z.object({ email: z.string().email("Enter a valid email") })),
  });

  const onLogin = loginForm.handleSubmit(async ({ email, password }) => {
    try {
      const token = await authApi.login(email, password);
      const user = await authApi.me();
      setAuth(token.access_token, user);
      navigate("/");
    } catch (err) {
      toast.error("Login failed", apiErrorMessage(err));
    }
  });

  const onRegister = registerForm.handleSubmit(async ({ email, password }) => {
    try {
      await authApi.register(email, password);
      const token = await authApi.login(email, password);
      const user = await authApi.me();
      setAuth(token.access_token, user);
      toast.success("Account created! Welcome 🎉");
      navigate("/");
    } catch (err) {
      toast.error("Registration failed", apiErrorMessage(err));
    }
  });

  const onForgot = forgotForm.handleSubmit(async ({ email }) => {
    try {
      const res = await authApi.forgotPassword(email);
      toast.success("Reset email sent", res.message);
      setMode("login");
    } catch (err) {
      toast.error("Failed", apiErrorMessage(err));
    }
  });

  const toggle = (m: "login" | "register") => {
    setMode(m);
    setShowPw(false);
    loginForm.reset();
    registerForm.reset();
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface p-4">
      {/* Background gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-brand/5 via-transparent to-transparent pointer-events-none" />

      <div className="w-full max-w-md relative">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-brand/20 border border-brand/30 flex items-center justify-center">
            <Code2 size={20} className="text-brand-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white leading-none">Basivo</h1>
            <p className="text-xs text-gray-500 mt-0.5">AI Coding Platform</p>
          </div>
        </div>

        {/* Card */}
        <div className="bg-surface-50 border border-gray-700/60 rounded-2xl shadow-2xl overflow-hidden">
          {/* Tabs */}
          {mode !== "forgot" && (
            <div className="flex border-b border-gray-700/50">
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => toggle(m)}
                  className={`flex-1 py-3 text-sm font-medium transition-colors capitalize ${
                    mode === m
                      ? "text-white border-b-2 border-brand bg-surface-200/40"
                      : "text-gray-400 hover:text-gray-200"
                  }`}
                >
                  {m === "login" ? "Sign In" : "Create Account"}
                </button>
              ))}
            </div>
          )}

          <div className="p-6">
            {/* ── LOGIN ───────────────────────────────────────────────────── */}
            {mode === "login" && (
              <form onSubmit={onLogin} className="flex flex-col gap-4">
                <Input
                  label="Email address"
                  type="email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  leftIcon={<Mail size={15} />}
                  error={loginForm.formState.errors.email?.message}
                  {...loginForm.register("email")}
                />
                <Input
                  label="Password"
                  type={showPw ? "text" : "password"}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  leftIcon={<Lock size={15} />}
                  rightSlot={
                    <button
                      type="button"
                      onClick={() => setShowPw((v) => !v)}
                      className="text-gray-500 hover:text-gray-300 transition-colors p-1"
                    >
                      {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  }
                  error={loginForm.formState.errors.password?.message}
                  {...loginForm.register("password")}
                />
                <button
                  type="button"
                  onClick={() => setMode("forgot")}
                  className="text-xs text-gray-500 hover:text-brand-400 text-right transition-colors -mt-1"
                >
                  Forgot password?
                </button>
                <Button
                  type="submit"
                  loading={loginForm.formState.isSubmitting}
                  className="w-full mt-1"
                >
                  Sign In <ArrowRight size={15} />
                </Button>
              </form>
            )}

            {/* ── REGISTER ────────────────────────────────────────────────── */}
            {mode === "register" && (
              <form onSubmit={onRegister} className="flex flex-col gap-4">
                <Input
                  label="Email address"
                  type="email"
                  placeholder="you@example.com"
                  autoComplete="email"
                  leftIcon={<Mail size={15} />}
                  error={registerForm.formState.errors.email?.message}
                  {...registerForm.register("email")}
                />
                <Input
                  label="Password"
                  type={showPw ? "text" : "password"}
                  placeholder="Min 8 chars, upper, lower, digit"
                  autoComplete="new-password"
                  leftIcon={<Lock size={15} />}
                  rightSlot={
                    <button type="button" onClick={() => setShowPw((v) => !v)} className="text-gray-500 hover:text-gray-300 p-1">
                      {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  }
                  error={registerForm.formState.errors.password?.message}
                  {...registerForm.register("password")}
                />
                <Input
                  label="Confirm password"
                  type={showConfirm ? "text" : "password"}
                  placeholder="Re-enter password"
                  autoComplete="new-password"
                  leftIcon={<Lock size={15} />}
                  rightSlot={
                    <button type="button" onClick={() => setShowConfirm((v) => !v)} className="text-gray-500 hover:text-gray-300 p-1">
                      {showConfirm ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  }
                  error={registerForm.formState.errors.confirmPassword?.message}
                  {...registerForm.register("confirmPassword")}
                />
                <PasswordStrength password={registerForm.watch("password") ?? ""} />
                <Button
                  type="submit"
                  loading={registerForm.formState.isSubmitting}
                  className="w-full mt-1"
                >
                  Create Account <ArrowRight size={15} />
                </Button>
              </form>
            )}

            {/* ── FORGOT PASSWORD ──────────────────────────────────────────── */}
            {mode === "forgot" && (
              <form onSubmit={onForgot} className="flex flex-col gap-4">
                <p className="text-sm text-gray-400">
                  Enter your email and we'll send you a reset link.
                </p>
                <Input
                  label="Email address"
                  type="email"
                  placeholder="you@example.com"
                  leftIcon={<Mail size={15} />}
                  error={forgotForm.formState.errors.email?.message}
                  {...forgotForm.register("email")}
                />
                <div className="flex gap-3 mt-1">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setMode("login")}
                    className="flex-1"
                  >
                    Back
                  </Button>
                  <Button
                    type="submit"
                    loading={forgotForm.formState.isSubmitting}
                    className="flex-1"
                  >
                    Send Reset Link
                  </Button>
                </div>
              </form>
            )}
          </div>
        </div>

        <p className="text-center text-xs text-gray-600 mt-4">
          Bring your own API key · Your keys are encrypted at rest
        </p>
      </div>
    </div>
  );
}

// ── Password strength indicator ───────────────────────────────────────────────

function PasswordStrength({ password }: { password: string }) {
  const checks = [
    { label: "8+ characters", ok: password.length >= 8 },
    { label: "Uppercase letter", ok: /[A-Z]/.test(password) },
    { label: "Lowercase letter", ok: /[a-z]/.test(password) },
    { label: "Digit", ok: /[0-9]/.test(password) },
  ];
  const score = checks.filter((c) => c.ok).length;
  const bar = ["bg-danger", "bg-warning", "bg-warning", "bg-success", "bg-success"][score];

  if (!password) return null;

  return (
    <div className="space-y-2">
      <div className="flex gap-1">
        {checks.map((_, i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-all ${i < score ? bar : "bg-gray-700"}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {checks.map((c) => (
          <span
            key={c.label}
            className={`text-xs ${c.ok ? "text-success" : "text-gray-500"}`}
          >
            {c.ok ? "✓" : "·"} {c.label}
          </span>
        ))}
      </div>
    </div>
  );
}
