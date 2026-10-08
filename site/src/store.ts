import type { Report, Input } from "./engine";
export type User = {
  id: string;
  name: string;
  email: string;
  platform: string;
  creator: string;
  onboarded: boolean;
  notifications: boolean;
};
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  let body: any;
  try {
    body = await response.json();
  } catch {
    throw new Error("The server is unavailable. Please try again.");
  }
  if (!response.ok) {
    if (response.status === 401 && body.detail === "Please log in to continue.")
      window.dispatchEvent(new Event("ts-session-expired"));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Something went wrong. Please try again.",
    );
  }
  return body as T;
}
export const me = () => api<{ user: User | null }>("/auth/me");
export const signup = (name: string, email: string, password: string) =>
  api<{ user: User; recoveryCode: string }>("/auth/signup", {
    method: "POST",
    body: JSON.stringify({ name, email, password, agree: true }),
  });
export const login = (email: string, password: string, remember: boolean) =>
  api<{ user: User }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password, remember }),
  });
export const logout = () => api("/auth/logout", { method: "POST" });
export const recover = (email: string, code: string, password: string) =>
  api<{ recoveryCode: string }>("/auth/recover", {
    method: "POST",
    body: JSON.stringify({ email, code, password }),
  });
export const reportsFor = (_id: string) => api<Report[]>("/reports");
export const reportFor = (id: string) =>
  api<Report>("/reports/" + encodeURIComponent(id));
export const persistReport = (_id: string, r: Report) =>
  api("/reports/" + encodeURIComponent(r.id) + "/save", { method: "POST" });
export const removeReport = (_id: string, r: Report) =>
  api("/reports/" + encodeURIComponent(r.id), { method: "DELETE" });
export const persistProfile = (u: User) =>
  api<{ user: User }>("/profile", { method: "PATCH", body: JSON.stringify(u) });
export const deleteAccount = (password: string) =>
  api("/account", { method: "DELETE", body: JSON.stringify({ password }) });
export const runAnalysis = (input: Input) =>
  api<Report>("/analyze", { method: "POST", body: JSON.stringify(input) });
export const usageFor = () =>
  api<{ count: number; limit: number; month: string }>("/usage");
