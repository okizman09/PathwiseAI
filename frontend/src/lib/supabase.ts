import { createClient } from '@supabase/supabase-js'

const supabaseUrl =
  (import.meta as any).env?.VITE_SUPABASE_URL ||
  'https://igpzvyetvyqxsfftmjzr.supabase.co'
const supabaseAnonKey =
  (import.meta as any).env?.VITE_SUPABASE_ANON_KEY ||
  'sb_publishable_G2qBkrdjIwhm5w0NydgvYw_GcvD5i5L'

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase URL or Anon Key is missing from environment variables.')
}

export const supabase = createClient(
  supabaseUrl,
  supabaseAnonKey
)
