import { defineConfig } from "orval";

/**
 * Generates a typed API client + TanStack Query hooks from the FastAPI
 * OpenAPI schema. Run with `npm run gen:api` (backend must be running,
 * or point OPENAPI_URL at a saved schema file).
 *
 * The generated hooks call our custom fetch mutator (`apiFetch`) so
 * every request goes through the same-origin BFF proxy (auth cookies).
 * Output lives in lib/api/generated/ (gitignored — regenerate on
 * contract changes).
 */
export default defineConfig({
  alostudio: {
    input: process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json",
    output: {
      mode: "tags-split",
      target: "lib/api/generated",
      schemas: "lib/api/generated/model",
      client: "react-query",
      httpClient: "fetch",
      clean: true,
      prettier: true,
      override: {
        mutator: {
          path: "./lib/api/fetcher.ts",
          name: "apiFetch",
        },
        query: {
          useQuery: true,
          useInfinite: false,
        },
      },
    },
  },
});
