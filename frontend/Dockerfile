# syntax=docker/dockerfile:1
#
# AloStudio frontend — production image (~150 MB).
# Uses Next.js standalone output (see next.config.mjs).
#
# Build:  docker build -t alostudio-frontend:latest frontend
# Run:    docker run --rm -p 3000:3000 \
#           -e BACKEND_INTERNAL_URL=http://backend:8000 \
#           -e NEXT_PUBLIC_API_BASE=/api/backend \
#           -e NEXT_PUBLIC_CABLE_URL=wss://api.example.com/cable \
#           alostudio-frontend:latest

# --- deps ----------------------------------------------------------
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# --- builder -------------------------------------------------------
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Vars consumed by the build (NEXT_PUBLIC_* are baked in at build time).
ARG NEXT_PUBLIC_API_BASE=/api/backend
ARG NEXT_PUBLIC_CABLE_URL=
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_CABLE_URL=$NEXT_PUBLIC_CABLE_URL
RUN npm run build

# --- runner --------------------------------------------------------
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Drop privileges
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001
USER nextjs

# Standalone output: copy only what's needed at runtime
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
