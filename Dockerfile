# ─── Build frontend ───────────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --production=false 2>/dev/null || npm install
COPY frontend/ ./
RUN npm run build

# ─── Runtime image ────────────────────────────────────────────
ARG BUILD_FROM
FROM $BUILD_FROM

# Install Python + deps
RUN apk add --no-cache \
    python3 \
    py3-pip \
    py3-aiohttp \
    sqlite \
    curl \
    tzdata

# Install Python packages
COPY backend/requirements.txt /tmp/
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

# Copy backend
COPY backend/ /app/backend/

# Copy built frontend
COPY --from=frontend-build /build/dist /app/frontend/dist

# Copy s6-overlay service definitions
COPY rootfs/ /

# Ensure data directory exists
RUN mkdir -p /data

WORKDIR /app
