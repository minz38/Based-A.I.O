# webhook_cog.py

import os
import json
import discord
import aiohttp
from discord import app_commands
from discord.ext import commands
from logger import LoggerManager

logger = LoggerManager(name="Webhook", level="INFO", log_file="logs/webhook.log").get_logger()


class WebhookCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def send_discord_webhook(webhook_url, content):
        async with aiohttp.ClientSession() as session:
            headers = {'Content-Type': 'application/json'}
            data = {'content': content}
            await session.post(webhook_url, headers=headers, data=json.dumps(data))

    @app_commands.command(name="webhook", description="Send a webhook notification")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def webhook(self, interaction: discord.Interaction, message: str, webhook: str) -> None:
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")

        if not webhook:
            await interaction.response.send_message("Error: Discord webhook URL not found.")  # noqa
            return

        await self.send_discord_webhook(webhook, message)
        await interaction.response.send_message("Webhook notification sent successfully.") # noqa


async def setup(bot):
    await bot.add_cog(WebhookCog(bot))
