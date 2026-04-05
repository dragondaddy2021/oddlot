import axios from "axios";
import { supabase } from "./supabase";

const api = axios.create({
  // In dev, use empty baseURL so Vite proxy handles /api/* (avoids CORS).
  // In production, use the explicit backend URL from the env var.
  baseURL: import.meta.env.DEV ? "" : (import.meta.env.VITE_API_BASE_URL ?? ""),
});

api.interceptors.request.use(async (config) => {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`;
  }
  return config;
});

export default api;
