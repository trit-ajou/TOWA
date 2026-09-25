FROM node:20-alpine

WORKDIR /app/towa-app

COPY towa-app/package.json ./

RUN npm install --legacy-peer-deps --no-audit --no-fund --maxsockets=1

WORKDIR /app

COPY bitmappery ./bitmappery
COPY towa-app ./towa-app

WORKDIR /app/towa-app

# Build-time public config. `vite build` bakes import.meta.env.VITE_* into the
# bundle, so these must be present at build time, not just runtime. compose passes
# them via build.args (see docker-compose.yml).
ARG VITE_DEPLOYMENT_MODE
ARG VITE_PUBLIC_HOST
ARG VITE_SERVICE_ENGINE_URL
ARG VITE_MODEL_ENGINE_URL
ARG VITE_UI_BACKEND_MODE
ARG VITE_UI_AUTH_BACKEND
ARG VITE_UI_AI_BACKEND
ARG VITE_UI_FILES_BACKEND
ENV VITE_DEPLOYMENT_MODE=$VITE_DEPLOYMENT_MODE \
    VITE_PUBLIC_HOST=$VITE_PUBLIC_HOST \
    VITE_SERVICE_ENGINE_URL=$VITE_SERVICE_ENGINE_URL \
    VITE_MODEL_ENGINE_URL=$VITE_MODEL_ENGINE_URL \
    VITE_UI_BACKEND_MODE=$VITE_UI_BACKEND_MODE \
    VITE_UI_AUTH_BACKEND=$VITE_UI_AUTH_BACKEND \
    VITE_UI_AI_BACKEND=$VITE_UI_AI_BACKEND \
    VITE_UI_FILES_BACKEND=$VITE_UI_FILES_BACKEND

RUN npm run build

EXPOSE 5173

# Production: serve the built bundle via Vite's preview server (no HMR / on-the-fly
# transforms). allowedHosts for the accessed host is set in vite.config.ts `preview`.
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
