# Build context is the repo root (see docker-compose.yml / .prod.yml) so the
# prod stage can also pull in frontend/nginx.conf alongside the built
# bundle without a second COPY source root.

# --- dev: used by docker-compose.yml. Code arrives via bind mount and runs
# through Vite's dev server with HMR. ---
FROM node:20-slim AS dev

WORKDIR /app

COPY frontend/package.json .
RUN npm install

COPY frontend/ .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# --- builder: compiles the production static bundle. ---
FROM node:20-slim AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json .
RUN npm ci

COPY frontend/ .
# VITE_API_BASE_URL is baked into the JS bundle at build time (Vite env
# vars aren't readable at container-start time like a backend's env vars
# are) — docker-compose.prod.yml passes it as a build arg.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build

# --- prod: used by docker-compose.prod.yml. Just the static bundle, served
# by an already-non-root nginx image — no Node, no source, no bind mount. ---
FROM nginxinc/nginx-unprivileged:1.27-alpine AS prod

COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080
