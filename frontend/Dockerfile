# --- Builder ---
FROM oven/bun:1-alpine AS builder
WORKDIR /app

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY . .
# `bun run build` is `vite build` alone: types are checked by `make front-lint`,
# which is where that gate lives. Doing it again here would be the same eight
# seconds paid a second time, on every rebuild.
RUN bun run build

# --- Runtime ---
FROM nginx:alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
