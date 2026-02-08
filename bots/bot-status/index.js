"use strict";

/**
 * Discord Status Bot
 * Fonctionnalités :
 *  - Résumé quotidien automatique du statut du serveur
 *  - Commandes !uptime et !serverstats
 *  - Affichage du nombre de membres et des membres en ligne
 */

require("dotenv").config();
const { Client, GatewayIntentBits, EmbedBuilder, ActivityType } = require("discord.js");
const cron = require("node-cron");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const DISCORD_TOKEN = process.env.DISCORD_TOKEN;
const GUILD_ID = process.env.GUILD_ID;
const STATUS_CHANNEL_ID = process.env.STATUS_CHANNEL_ID;

if (!DISCORD_TOKEN || !GUILD_ID || !STATUS_CHANNEL_ID) {
  console.error(
    "[FATAL] Variables d'environnement manquantes : DISCORD_TOKEN, GUILD_ID, STATUS_CHANNEL_ID"
  );
  process.exit(1);
}

// Heure d'envoi du rapport quotidien (format cron : 09:00 chaque jour)
const DAILY_REPORT_CRON = process.env.DAILY_REPORT_CRON || "0 9 * * *";

// Timestamp de démarrage du bot
const BOT_START_TIME = Date.now();

// ---------------------------------------------------------------------------
// Client Discord
// ---------------------------------------------------------------------------

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildPresences,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
});

// ---------------------------------------------------------------------------
// Utilitaires
// ---------------------------------------------------------------------------

/**
 * Formate une durée en millisecondes en chaîne lisible (j h m s).
 * @param {number} ms
 * @returns {string}
 */
function formatUptime(ms) {
  const totalSeconds = Math.floor(ms / 1000);
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  const parts = [];
  if (days > 0) parts.push(`${days}j`);
  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}m`);
  parts.push(`${seconds}s`);

  return parts.join(" ");
}

/**
 * Récupère les statistiques du serveur Discord.
 * @param {import("discord.js").Guild} guild
 * @returns {{ total: number, online: number, idle: number, dnd: number, offline: number }}
 */
async function getGuildStats(guild) {
  // S'assurer que les membres et présences sont chargés
  await guild.members.fetch();

  const total = guild.memberCount;
  let online = 0;
  let idle = 0;
  let dnd = 0;

  guild.members.cache.forEach((member) => {
    const status = member.presence?.status;
    if (status === "online") online++;
    else if (status === "idle") idle++;
    else if (status === "dnd") dnd++;
  });

  const offline = total - online - idle - dnd;

  return { total, online, idle, dnd, offline };
}

/**
 * Construit un embed de rapport de statut du serveur.
 * @param {import("discord.js").Guild} guild
 * @param {boolean} isDaily
 * @returns {Promise<EmbedBuilder>}
 */
async function buildStatusEmbed(guild, isDaily = false) {
  const stats = await getGuildStats(guild);
  const now = new Date();

  const embed = new EmbedBuilder()
    .setTitle(isDaily ? "📊 Rapport quotidien du serveur" : "📊 Statistiques du serveur")
    .setColor(0x5865f2) // Bleu Discord
    .setThumbnail(guild.iconURL({ dynamic: true }) ?? null)
    .addFields(
      {
        name: "👥 Membres total",
        value: `**${stats.total}**`,
        inline: true,
      },
      {
        name: "🟢 En ligne",
        value: `**${stats.online}**`,
        inline: true,
      },
      {
        name: "🌙 Inactif",
        value: `**${stats.idle}**`,
        inline: true,
      },
      {
        name: "🔴 Ne pas déranger",
        value: `**${stats.dnd}**`,
        inline: true,
      },
      {
        name: "⚫ Hors ligne",
        value: `**${stats.offline}**`,
        inline: true,
      },
      {
        name: "📅 Serveur créé",
        value: `<t:${Math.floor(guild.createdTimestamp / 1000)}:R>`,
        inline: true,
      }
    )
    .setFooter({
      text: `${guild.name} · Rapport automatique`,
      iconURL: guild.iconURL({ dynamic: true }) ?? undefined,
    })
    .setTimestamp(now);

  if (isDaily) {
    embed.setDescription(
      `Rapport automatique généré le **${now.toLocaleDateString("fr-FR", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      })}** à **${now.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}**`
    );
  }

  return embed;
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------

client.once("ready", async () => {
  console.log(`[INFO] Bot connecté : ${client.user.tag} (ID ${client.user.id})`);

  const guild = client.guilds.cache.get(GUILD_ID);
  if (!guild) {
    console.error(`[ERROR] Serveur avec l'ID ${GUILD_ID} introuvable.`);
  } else {
    console.log(`[INFO] Serveur cible : ${guild.name} (${guild.memberCount} membres)`);
  }

  client.user.setPresence({
    activities: [
      {
        name: "le statut du serveur | !help",
        type: ActivityType.Watching,
      },
    ],
    status: "online",
  });

  // Planifier le rapport quotidien
  cron.schedule(
    DAILY_REPORT_CRON,
    async () => {
      try {
        const targetGuild = client.guilds.cache.get(GUILD_ID);
        if (!targetGuild) return;

        const channel = targetGuild.channels.cache.get(STATUS_CHANNEL_ID);
        if (!channel || !channel.isTextBased()) return;

        const embed = await buildStatusEmbed(targetGuild, true);
        await channel.send({ embeds: [embed] });
        console.log("[INFO] Rapport quotidien envoyé.");
      } catch (err) {
        console.error("[ERROR] Impossible d'envoyer le rapport quotidien :", err);
      }
    },
    {
      timezone: "Europe/Paris",
    }
  );

  console.log(`[INFO] Rapport quotidien planifié : ${DAILY_REPORT_CRON} (Europe/Paris)`);
});

client.on("messageCreate", async (message) => {
  if (message.author.bot) return;
  if (!message.guild) return;

  const args = message.content.trim().split(/\s+/);
  const command = args[0].toLowerCase();

  // -------------------------------------------------------------------------
  // !uptime — Affiche l'uptime du bot
  // -------------------------------------------------------------------------
  if (command === "!uptime") {
    const botUptime = formatUptime(Date.now() - BOT_START_TIME);
    const processUptime = formatUptime(process.uptime() * 1000);
    const latency = Math.round(client.ws.ping);

    const embed = new EmbedBuilder()
      .setTitle("⏱️ Uptime du bot")
      .setColor(0x57f287) // Vert
      .addFields(
        { name: "🤖 Bot actif depuis", value: `**${botUptime}**`, inline: true },
        { name: "⚙️ Processus Node.js", value: `**${processUptime}**`, inline: true },
        { name: "📡 Latence API", value: `**${latency} ms**`, inline: true }
      )
      .setTimestamp()
      .setFooter({ text: `Demandé par ${message.author.tag}` });

    await message.reply({ embeds: [embed] });
    return;
  }

  // -------------------------------------------------------------------------
  // !serverstats — Affiche les statistiques du serveur
  // -------------------------------------------------------------------------
  if (command === "!serverstats") {
    try {
      const embed = await buildStatusEmbed(message.guild, false);
      await message.reply({ embeds: [embed] });
    } catch (err) {
      console.error("[ERROR] Erreur !serverstats :", err);
      await message.reply("❌ Impossible de récupérer les statistiques du serveur.");
    }
    return;
  }

  // -------------------------------------------------------------------------
  // !botinfo — Informations sur le bot
  // -------------------------------------------------------------------------
  if (command === "!botinfo") {
    const memUsage = process.memoryUsage();
    const embed = new EmbedBuilder()
      .setTitle("🤖 Informations du bot")
      .setColor(0x5865f2)
      .setThumbnail(client.user.displayAvatarURL())
      .addFields(
        { name: "Nom", value: client.user.tag, inline: true },
        { name: "ID", value: client.user.id, inline: true },
        { name: "Node.js", value: process.version, inline: true },
        {
          name: "Mémoire RSS",
          value: `${Math.round(memUsage.rss / 1024 / 1024)} Mo`,
          inline: true,
        },
        {
          name: "Heap utilisé",
          value: `${Math.round(memUsage.heapUsed / 1024 / 1024)} Mo`,
          inline: true,
        },
        {
          name: "Serveurs",
          value: `${client.guilds.cache.size}`,
          inline: true,
        }
      )
      .setTimestamp()
      .setFooter({ text: "bot-status v1.0.0" });

    await message.reply({ embeds: [embed] });
    return;
  }
});

// ---------------------------------------------------------------------------
// Gestion des erreurs
// ---------------------------------------------------------------------------

client.on("error", (err) => {
  console.error("[ERROR] Erreur client Discord :", err);
});

process.on("unhandledRejection", (reason) => {
  console.error("[ERROR] Promesse non gérée :", reason);
});

process.on("SIGTERM", () => {
  console.log("[INFO] Signal SIGTERM reçu — arrêt propre.");
  client.destroy();
  process.exit(0);
});

process.on("SIGINT", () => {
  console.log("[INFO] Signal SIGINT reçu — arrêt propre.");
  client.destroy();
  process.exit(0);
});

// ---------------------------------------------------------------------------
// Démarrage
// ---------------------------------------------------------------------------

client.login(DISCORD_TOKEN).catch((err) => {
  console.error("[FATAL] Impossible de se connecter à Discord :", err.message);
  process.exit(1);
});
