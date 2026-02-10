# ─────────────────────────────────────────────
# Stage 1 — Builder : installation des dépendances
# ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Variables d'environnement pour pip
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# Copier uniquement le fichier de dépendances pour bénéficier du cache Docker
COPY requirements.txt .

# Installer les dépendances dans un répertoire isolé
RUN pip install --prefix=/install -r requirements.txt


# ─────────────────────────────────────────────
# Stage 2 — Runtime : image finale allégée
# ─────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Métadonnées
LABEL org.opencontainers.image.title="bot-moderation" \
      org.opencontainers.image.description="Discord moderation bot (discord.py)" \
      org.opencontainers.image.source="https://github.com/VOTRE_USERNAME/discord-bots-infra"

# Variables d'environnement Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HEALTH_PORT=8080

# Créer un utilisateur non-root dédié
RUN groupadd --gid 1001 botgroup && \
    useradd --uid 1001 --gid botgroup --no-create-home --shell /sbin/nologin botuser

WORKDIR /app

# Copier les dépendances installées depuis le builder
COPY --from=builder /install /usr/local

# Copier le code source
COPY --chown=botuser:botgroup main.py .

# Utiliser l'utilisateur non-root
USER botuser

# Exposer le port du health check
EXPOSE 8080

# Health check Docker natif
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["python", "main.py"]
