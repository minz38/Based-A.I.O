import discord
from discord.ext import commands
from discord import app_commands
from dep.logger import LoggerManager

logger = LoggerManager(name="Sync", level="INFO", log_name="bot").get_logger()


class SyncConfirmView(discord.ui.View):
    def __init__(self, interaction, channel, admin_log_cog):
        super().__init__()
        self.interaction = interaction
        self.channel = channel
        self.admin_log_cog = admin_log_cog

    @discord.ui.button(label='Proceed', style=discord.ButtonStyle.green)
    async def proceed_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Ensure only the user who initiated the command can proceed
        if interaction.user != self.interaction.user:
            await interaction.response.send_message("You are not allowed to use this.", ephemeral=True)  # noqa
            return

        try:
            await self.channel.edit(sync_permissions=True)
            await interaction.response.edit_message(  # noqa
                content="Channel permissions synchronized with the category.",
                view=None)
            logger.info(f"Synced: Channel {self.channel.mention} with Category {self.channel.category.name}")

            if self.admin_log_cog:
                await self.admin_log_cog.log_interaction(
                    self.interaction,
                    text=f"Synced: Channel {self.channel.mention} with Category {self.channel.category.mention}",
                    priority="info"
                )
        except Exception as e:
            await interaction.response.edit_message(  # noqa
                content="Failed to sync channel permissions with the category.",
                view=None)

            logger.error(
                f"Failed to sync: Channel {self.channel.mention} with Category {self.channel.category.name} - {e}")

        self.stop()

    @discord.ui.button(label='Abort', style=discord.ButtonStyle.red)
    async def abort_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Ensure only the user who initiated the command can abort
        if interaction.user != self.interaction.user:
            await interaction.response.send_message("You are not allowed to use this.", ephemeral=True)  # noqa
            return

        await interaction.response.edit_message(content="Operation cancelled.", view=None)  # noqa
        logger.info(f"User {self.interaction.user.name} cancelled the sync operation.")
        self.stop()


class Sync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='sync', description='Sync channel permissions with the channels Category')
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.guild_only()
    async def sync_channels(self, interaction: discord.Interaction) -> None:
        admin_log_cog = self.bot.get_cog("AdminLog")
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        channel: discord.TextChannel = interaction.channel

        if not channel.category or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(  # noqa
                "This channel doesn't belong to a category.",
                ephemeral=True
            )
            logger.error(f"Channel {channel.mention} doesn't belong to a category.")
            return

        def format_overwrites(overwrites):
            lines = []
            for target, overwrite in overwrites.items():
                permissions = []
                if overwrite.view_channel is True:
                    permissions.append('View Channel: ✅')
                elif overwrite.view_channel is False:
                    permissions.append('View Channel: ❌')
                else:
                    continue  # Skip if view_channel is not explicitly set

                line = f"{target.mention} - {', '.join(permissions)}"
                lines.append(line)
            return '\n'.join(lines) if lines else "No specific permissions set."

        current_overwrites_str = format_overwrites(channel.overwrites)
        category_overwrites_str = format_overwrites(channel.category.overwrites)

        message_content = (
            "All current channel permissions will be **overwritten** with the default permissions of this category. "
            "This step is **irreversible**, and if there are users or roles already specified for this channel, "
            "they will be overwritten and may lose access.\n\n"
            "**Current Channel Permissions:**\n"
            f"{current_overwrites_str}\n\n"
            "**Permissions After Syncing:**\n"
            f"{category_overwrites_str}\n\n"
            "Do you want to proceed?"
        )

        view = SyncConfirmView(interaction, channel, admin_log_cog)
        await interaction.response.send_message(content=message_content, view=view, ephemeral=True)  # noqa


async def setup(bot):
    await bot.add_cog(Sync(bot))
