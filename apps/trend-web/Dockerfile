# Next.js standalone image. API address and data mode are runtime settings.
FROM node:24.21.0-bookworm-slim AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN corepack pnpm install --frozen-lockfile
COPY . .
# public/ has no tracked files yet, so a fresh checkout has no such directory; the runtime stage copies it.
RUN mkdir -p public && corepack pnpm build

FROM node:24.21.0-bookworm-slim
WORKDIR /app
ENV NODE_ENV=production PORT=8080 HOSTNAME=0.0.0.0 DATA_MODE=sample
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
CMD ["node", "server.js"]
