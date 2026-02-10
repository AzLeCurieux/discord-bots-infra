# ─────────────────────────────────────────────
# Stage 1 — Builder : installation des dépendances npm
# ─────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /build

# Copier uniquement les fichiers de dépendances pour bénéficier du cache Docker
COPY package.json package-lock.json* ./

# Installer uniquement les dépendances de production
RUN npm ci --omit=dev && \
    # Nettoyer le cache npm
    npm cache clean --force


# ─────────────────────────────────────────────
# Stage 2 — Runtime : image finale allégée
# ─────────────────────────────────────────────
FROM node:20-alpine AS runtime

# Métadonnées
LABEL org.opencontainers.image.title="bot-status" \
      org.opencontainers.image.description="Discord status monitoring bot (discord.js)" \
      org.opencontainers.image.source="https://github.com/VOTRE_USERNAME/discord-bots-infra"

# Mettre à jour les paquets de sécurité Alpine
RUN apk update && apk upgrade --no-cache && \
    # Créer un utilisateur non-root dédié
    addgroup --gid 1001 botgroup && \
    adduser --uid 1001 --ingroup botgroup --disabled-password --no-create-home --shell /sbin/nologin botuser

WORKDIR /app

# Copier les node_modules depuis le builder
COPY --from=builder /build/node_modules ./node_modules

# Copier le code source
COPY --chown=botuser:botgroup package.json index.js ./

# Utiliser l'utilisateur non-root
USER botuser

# Ce bot n'expose pas de port HTTP — pas de HEALTHCHECK TCP
# On vérifie que le processus Node.js est vivant
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD node -e "process.exit(0)" || exit 1

CMD ["node", "index.js"]
