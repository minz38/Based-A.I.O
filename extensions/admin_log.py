import os
import json
import discord
from datetime import datetime
from discord import app_commands
from discord.ext import commands
from logger import LoggerManager
from typing import Literal

logger = LoggerManager(name="Admin Log", level="INFO", log_file="logs/admin_log.log").get_logger()


class AdminLog(commands.Cog):
    def __init__(self, bot: commands.Bot, interaction: discord.Interaction = None) -> None:
        self.bot = bot
        self.interaction = interaction
        self.log_channels: dict[discord.Guild.id, discord.TextChannel] = {}

    @staticmethod
    async def match_priority(priority: Literal["info", "warn", "error"]) -> discord.Color:
        match priority:
            case "info":
                return discord.Color.green()
            case "warn":
                return discord.Color.orange()
            case "error":
                return discord.Color.red()
            case _:
                return discord.Color.default()

    async def log_interaction(self, interaction: discord.Interaction,
                              priority: Literal["info", "warn", "error"],
                              text: str | None = None) -> None:
        log_channel = await self.get_admin_log_channel(interaction.guild.id)
        if log_channel is None:
            return

        short_timestamp = interaction.created_at.strftime("%d.%m.%Y %H:%M")

        color = await self.match_priority(priority)
        embed = discord.Embed(title=f"Bot Command Used")
        embed.colour = color
        embed.add_field(name="Command", value=f'/{interaction.command.name}', inline=True)
        embed.add_field(name="User", value=interaction.user.display_name, inline=True)
        if text:
            embed.add_field(name="Note", value=text, inline=False)
        embed.set_footer(text=f"Timestamp: {short_timestamp}")
        await log_channel.send(embed=embed)

    async def log_event(self, guild_id: int,
                        priority: Literal["info", "warn", "error"],
                        event_name: str, event_status: str = None) -> None:
        log_channel = await self.get_admin_log_channel(guild_id)

        if log_channel is None:
            return

        color = await self.match_priority(priority)
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
        embed = discord.Embed(title=f"Bot Event")
        embed.colour = color
        embed.add_field(name="Event:", value=event_name, inline=True)
        if event_status:
            embed.add_field(name="Status:", value=event_status, inline=False)
        embed.set_footer(text=f"Timestamp: {timestamp}")
        await log_channel.send(embed=embed)

    async def get_admin_log_channel(self, guild_id: int) -> None | discord.TextChannel:
        with open(f"configs/guilds/{guild_id}.json", "r") as file:
            guild_config = json.load(file)
            guild: discord.Guild = self.bot.get_guild(guild_id)

        if "admin_log_channel" in guild_config:
            log_channel: discord.TextChannel = self.bot.get_channel(int(guild_config["admin_log_channel"]))
            if log_channel is None:
                logger.error(f"Admin log channel not found for guild: {guild.name}")
                return None
            else:
                return log_channel
        else:
            logger.debug(f"Admin log key is nor present in the guild config file")
            return None

    @app_commands.command(name="admin_log", description="Set the admin log channel for this Bot")
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.choices(status=[app_commands.Choice(name="enable", value="enable"),
                                  app_commands.Choice(name="disable", value="disable")])
    async def setup_log_channel(self,
                                interaction: discord.Interaction,
                                log_channel: discord.TextChannel = None,
                                status: str = None) -> None:

        path = f"configs/guilds/{interaction.guild.id}.json"
        with open(path, "r") as file:
            data = json.load(file)
        match status:
            case "enable":
                if log_channel:
                    if "admin_log_channel" not in data:
                        data["admin_log_channel"] = str(log_channel.id)

                        with open(path, "w") as file:
                            json.dump(data, file, indent=4)

                        await interaction.response.send_message(  # noqa
                            f"Admin log channel set to {log_channel.mention}")
                        await self.log_interaction(interaction, f"Bot log channel set to {log_channel.mention}")
                else:
                    await interaction.response.send_message("Please specify an admin log channel.")  # noqa
                    logger.error("No admin log channel specified during admin log setup.")
            case "disable":
                await self.log_interaction(interaction, "Bot log channel disabled.")
                data.pop("admin_log_channel", None)

                with open(path, "w") as file:
                    json.dump(data, file, indent=4)

                await interaction.response.send_message("Admin log channel disabled.")  # noqa

            case _:
                await interaction.response.send_message("Invalid status. Please choose 'enable' or 'disable'.")  # noqa
                logger.error(f"Invalid status during admin log setup. Status: {status}")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminLog(bot))
