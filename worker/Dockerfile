# Worker image: Celery + the static-analysis toolchain (Java, apktool, jadx).
# All tool invocations happen here so the Windows host stays clean — nothing
# needs installing outside Docker Desktop.
FROM python:3.12-slim

ARG APKTOOL_VERSION=2.9.3
ARG JADX_VERSION=1.5.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openjdk-21-jre-headless \
        curl \
        unzip \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# --- apktool (unpacks APKs: manifest, resources, smali) ---
RUN mkdir -p /opt/tools/apktool \
    && curl -fsSL -o /opt/tools/apktool/apktool.jar \
        "https://github.com/iBotPeaches/Apktool/releases/download/v${APKTOOL_VERSION}/apktool_${APKTOOL_VERSION}.jar" \
    && printf '#!/bin/sh\nexec java -jar /opt/tools/apktool/apktool.jar "$@"\n' > /usr/local/bin/apktool \
    && chmod +x /usr/local/bin/apktool

# --- jadx (decompiles APK -> readable Java) ---
RUN mkdir -p /opt/tools/jadx \
    && curl -fsSL -o /tmp/jadx.zip \
        "https://github.com/skylot/jadx/releases/download/v${JADX_VERSION}/jadx-${JADX_VERSION}.zip" \
    && unzip -q /tmp/jadx.zip -d /opt/tools/jadx \
    && rm /tmp/jadx.zip \
    && chmod +x /opt/tools/jadx/bin/jadx /opt/tools/jadx/bin/jadx-gui \
    && ln -s /opt/tools/jadx/bin/jadx /usr/local/bin/jadx

WORKDIR /worker

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/worker:/app \
    TOOLS_CACHE_DIR=/opt/tools-cache

CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
