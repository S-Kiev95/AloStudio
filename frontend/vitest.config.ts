import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    // The second pattern is for ``middleware.ts``, which Next requires at
    // the project root and which is the only thing standing between a
    // signed-out visitor and the dashboard.
    include: [
      "{app,lib,components}/**/*.{test,spec}.{ts,tsx}",
      "*.{test,spec}.{ts,tsx}",
    ],
    globals: true,
  },
});
