import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
from pathlib import Path
import asyncio


class AutoDeleteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_delete_tasks = {}
        self.load_all_configs()

    # Utility function to get the config path for each guild
    def get_config_path(self, guild_id):
        return Path(f"configs/guilds/{guild_id}.json")

    # Load all configurations on startup
    def load_all_configs(self):
        for guild in self.bot.guilds:
            self.load_guild_config(guild.id)

    # Load configuration for a specific guild
    def load_guild_config(self, guild_id):
        config_path = self.get_config_path(guild_id)
        if config_path.is_file():
            with open(config_path, "r") as file:
                config = json.load(file)
            auto_delete_channels = config.get("auto_delete_channels", {})
            for channel_id, hours in auto_delete_channels.items():
                self.schedule_auto_delete(int(channel_id), int(hours))

    # Save only the auto-delete config without modifying other settings
    def save_auto_delete_config(self, guild_id, auto_delete_channels):
        config_path = self.get_config_path(guild_id)
        config = {}

        # Load existing config if it exists
        if config_path.is_file():
            with open(config_path, "r") as file:
                config = json.load(file)

        # Update only the auto_delete_channels section
        config["auto_delete_channels"] = auto_delete_channels
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as file:
            json.dump(config, file, indent=4)

    # Helper function to schedule the auto-delete task
    def schedule_auto_delete(self, channel_id, hours):
        if channel_id in self.auto_delete_tasks:
            self.auto_delete_tasks[channel_id].cancel()
        task = asyncio.create_task(self.auto_delete_task(channel_id, hours))
        self.auto_delete_tasks[channel_id] = task

    # Individual auto-delete task for each channel
    async def auto_delete_task(self, channel_id, hours):
        await self.bot.wait_until_ready()
        while True:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    async for message in channel.history(limit=None):
                        if not message.pinned and not message.author.bot:
                            await message.delete()
                except Exception as e:
                    print(f"Error deleting messages in {channel.name}: {e}")
            else:
                print(f"Channel ID {channel_id} not found.")
                break
            await asyncio.sleep(hours * 60)  # Convert hours to seconds

    # Define a Group for auto_delete commands
    auto_delete_group = app_commands.Group(
        name="auto_delete",
        description="Manage automatic message deletion."
    )

    # Subcommand to enable auto-delete
    @auto_delete_group.command(name="enable", description="Enable automatic message deletion for this channel.")
    @app_commands.describe(hours="Time interval in hours for deleting messages.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def enable(self, interaction: discord.Interaction, hours: int):
        channel_id = interaction.channel_id
        guild_id = interaction.guild_id
        config_path = self.get_config_path(guild_id)

        if hours <= 0:
            await interaction.response.send_message("Please provide a valid number of hours (> 0).", ephemeral=True)
            return

        # Load existing config or initialize a new one
        auto_delete_channels = {}
        if config_path.is_file():
            with open(config_path, "r") as file:
                config = json.load(file)
            auto_delete_channels = config.get("auto_delete_channels", {})

        # Update the config with new auto-delete settings
        auto_delete_channels[str(channel_id)] = hours
        self.save_auto_delete_config(guild_id, auto_delete_channels)

        # Schedule the auto-delete task
        self.schedule_auto_delete(channel_id, hours)

        await interaction.response.send_message(
            f"🟢 Automatic message deletion enabled for this channel every {hours} hour(s).", ephemeral=True
        )

    # Subcommand to disable auto-delete
    @auto_delete_group.command(name="disable", description="Disable automatic message deletion for this channel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def disable(self, interaction: discord.Interaction):
        channel_id = interaction.channel_id
        guild_id = interaction.guild_id
        config_path = self.get_config_path(guild_id)

        # Load config
        if not config_path.is_file():
            await interaction.response.send_message("🔴 Automatic message deletion is not enabled for this channel.",
                                                    ephemeral=True)
            return

        with open(config_path, "r") as file:
            config = json.load(file)

        auto_delete_channels = config.get("auto_delete_channels", {})

        # Remove the channel from auto-delete settings if it exists
        if str(channel_id) in auto_delete_channels:
            del auto_delete_channels[str(channel_id)]
            self.save_auto_delete_config(guild_id, auto_delete_channels)

            # Cancel the scheduled task if it's running
            if channel_id in self.auto_delete_tasks:
                self.auto_delete_tasks[channel_id].cancel()
                del self.auto_delete_tasks[channel_id]

            await interaction.response.send_message("🔴 Automatic message deletion disabled for this channel.",
                                                    ephemeral=True)
        else:
            await interaction.response.send_message("🔴 Automatic message deletion is not enabled for this channel.",
                                                    ephemeral=True)

    # Subcommand to check the status of auto-delete
    @auto_delete_group.command(name="status", description="View auto-delete settings for this guild.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        config_path = self.get_config_path(guild_id)

        # Load config
        if config_path.is_file():
            with open(config_path, "r") as file:
                config = json.load(file)
            auto_delete_channels = config.get("auto_delete_channels", {})

            if auto_delete_channels:
                message = "📄 **Auto-Delete Settings:**\n"
                for chan_id, hrs in auto_delete_channels.items():
                    channel = self.bot.get_channel(int(chan_id))
                    if channel:
                        message += f"🔹 {channel.mention} - Every {hrs} hour(s)\n"
                    else:
                        message += f"🔹 Channel ID {chan_id} (Not Found) - Every {hrs} hour(s)\n"
                await interaction.response.send_message(message, ephemeral=True)
            else:
                await interaction.response.send_message("📄 No channels have auto-delete enabled.", ephemeral=True)
        else:
            await interaction.response.send_message("📄 No channels have auto-delete enabled.", ephemeral=True)


    # Ensure tasks are cancelled when the cog is unloaded
    def cog_unload(self):
        for task in self.auto_delete_tasks.values():
            task.cancel()


async def setup(bot):
    await bot.add_cog(AutoDeleteCog(bot))
