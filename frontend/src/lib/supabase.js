import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  // Log clearly in development; do not throw so the app still renders
  // with a degraded state instead of a blank white screen.
  console.error(
    "[oddlot] Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY.\n" +
    "Copy .env.example to .env and fill in the Supabase credentials."
  );
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
