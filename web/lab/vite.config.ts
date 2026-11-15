import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({ plugins: [react()], envDir: "/__epochguard_no_env__", build: { sourcemap: false } });
