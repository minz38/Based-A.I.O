import re
import json
import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.utils import escape_mentions
from bot import bot as shadow_bot
from logger import LoggerManager

logger = LoggerManager(name="Archive", level="INFO", log_file="logs/Archive.log").get_logger()


class ArchiveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="archive", description="Archive the current channel")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def archive(self, interaction: discord.Interaction):
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        admin_log_cog = interaction.client.get_cog("AdminLog")

        # Defer the response to give the bot time to process
        await interaction.response.defer(ephemeral=True)

        # Get the current channel
        channel = interaction.channel

        # Ensure the command is used in a text channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("This command can only be used in a text channel.", ephemeral=True)
            return

        # Load the archive category ID from the guild's config
        guild_id = interaction.guild.id
        config_file = f'configs/guilds/{guild_id}.json'
        if not os.path.exists(config_file):
            await interaction.followup.send(
                "No configuration file found for this guild. Please set up the archive category using `/set_archive`.",
                ephemeral=True)
            return

        with open(config_file, 'r') as f:
            guild_config = json.load(f)

        archive_category_id = guild_config.get('archive_category_id')
        if not archive_category_id:
            await interaction.followup.send("No archive category set. Please use `/set_archive` to set it.",
                                            ephemeral=True)
            return

        # Fetch the archive category
        archive_category = interaction.guild.get_channel(archive_category_id)
        if not isinstance(archive_category, discord.CategoryChannel):
            await interaction.followup.send(
                "The archive category ID stored is invalid. Please set it again using `/set_archive`.", ephemeral=True)
            return

        if admin_log_cog:
            await admin_log_cog.log_interaction(interaction=interaction,
                                                priority="warn",
                                                text=f"Channel {channel.name} will be archived to: "
                                                     f"{archive_category.name}.")

        # Collect current permission settings and print them
        previous_overwrites = channel.overwrites.copy()
        logger.info(f"Current permissions: {previous_overwrites}")
        for target, overwrite in previous_overwrites.items():
            logger.info(f"Permission overwrite for {target}: {overwrite}")

        # Get members who can currently see the channel
        members_with_access = []
        for member in channel.guild.members:
            permissions = channel.permissions_for(member)
            if permissions.read_messages:
                members_with_access.append(member)

        # Save the previous category
        previous_category = channel.category

        # Remove role permissions (except @everyone) and replace with per-user permissions
        for target in list(channel.overwrites):
            if isinstance(target, discord.Role) and target != channel.guild.default_role:  # ignore @everyone
                await channel.set_permissions(target, overwrite=None)

        # Explicitly deny @everyone from seeing the channel
        await channel.set_permissions(channel.guild.default_role, read_messages=False)

        # Grant read and send permissions to users who had access
        for member in members_with_access:
            await channel.set_permissions(
                member,
                overwrite=discord.PermissionOverwrite(
                    read_messages=True, send_messages=True
                )
            )

        # Move the channel to the archive category
        await channel.edit(category=archive_category)

        # Prepare data for restoring
        previous_permission_data = []
        for target, overwrite in previous_overwrites.items():
            target_data = {
                'i': target.id,
                't': 'r' if isinstance(target, discord.Role) else 'm',  # 'r' for role, 'm' for member
                'a': overwrite.pair()[0].value,
                'd': overwrite.pair()[1].value
            }
            previous_permission_data.append(target_data)

        # Include previous category info
        previous_category_data = {
            'i': previous_category.id if previous_category else None,
            'n': previous_category.name if previous_category else None
        }

        # Create a JSON object
        archive_data = {
            'pre_perm': previous_permission_data,
            'pre_cat': previous_category_data
        }

        # Send the archive message in the channel
        archive_message = (
            "This channel has been archived:\n\n"
            f"*Restore code:*"
            f"```json\n{json.dumps(archive_data)}\n```"
        )
        await channel.send(archive_message)

        # Inform the user that the channel has been archived
        await interaction.followup.send("Channel has been archived.", ephemeral=True)
        if admin_log_cog:
            await admin_log_cog.log_interaction(interaction=interaction,
                                                priority="info",
                                                text=f"Channel {channel.name} archived.")

    @app_commands.command(name="set_archive", description="Set the archive category for this guild")
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_archive(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        admin_log_cog = interaction.client.get_cog("AdminLog")
        if admin_log_cog:
            await admin_log_cog.log_interaction(interaction=interaction,
                                                priority="info",
                                                text=f"Set archive category for guild {interaction.guild.name} to"
                                                     f" {category.name}.")
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        guild_id = interaction.guild.id
        config_file = f'configs/guilds/{guild_id}.json'

        # Load existing config or create a new one
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                guild_config = json.load(f)
        else:
            guild_config = {}

        # Update the archive category ID
        guild_config['archive_category_id'] = category.id

        # Save the updated config
        with open(config_file, 'w') as f:
            json.dump(guild_config, f, indent=4)

        await interaction.response.send_message(f"Archive category set to {category.name}.", ephemeral=True)  # noqa
        logger.info(f"Archive category set to {category.name} ({category.id}) for guild {interaction.guild.name}")


@app_commands.guild_only()
@app_commands.checks.has_permissions(manage_channels=True)
@shadow_bot.tree.context_menu(name="Restore Channel")
async def restore_channel(interaction: discord.Interaction, message: discord.Message) -> None:
    logger.info(f"Command: {interaction.command.name} used by {interaction.user.name} on message id: {message.id}")
    admin_log_cog = interaction.client.get_cog("AdminLog")  # shadow_bot.get_cog("AdminLog")

    # Defer the response
    await interaction.response.defer(ephemeral=True)  # noqa

    # Ensure the message is from the bot and contains the archive data
    if message.author != shadow_bot.user:
        await interaction.followup.send("This message was not sent by the bot.", ephemeral=True)
        return

    # Ensure the message is in a text channel
    channel = message.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send("This command can only be used in a text channel.", ephemeral=True)
        return

    # Parse the archive data from the message content
    try:
        content = message.content
        # Extract the JSON data from the code block
        pattern = r'```json\s*(\{.*?\})\s*```'
        matches = re.findall(pattern, content, re.DOTALL)
        if not matches:
            raise ValueError("Archive data not found in message.")

        json_data = matches[-1]
        archive_data = json.loads(json_data)

    except ValueError as _:
        await interaction.followup.send("Failed to parse archive data from the message.", ephemeral=True)
        return

    # Restore the previous permissions
    previous_permissions = archive_data.get('pre_perm', [])
    for perm_data in previous_permissions:
        target_id = perm_data.get('i')  # id
        target_type = perm_data.get('t')  # type
        allow_value = perm_data.get('a')  # allow
        deny_value = perm_data.get('d')  # deny

        if target_type == 'r':
            target = interaction.guild.get_role(target_id)
        elif target_type == 'm':
            target = interaction.guild.get_member(target_id)
        else:
            target = None

        if target is None:
            # Skip if target no longer exists
            continue

        # Create PermissionOverwrite from allow and deny values
        overwrite = discord.PermissionOverwrite.from_pair(
            discord.Permissions(allow_value),
            discord.Permissions(deny_value)
        )

        await channel.set_permissions(target, overwrite=overwrite)

    # Remove per-user permissions set during archiving
    for member in channel.overwrites:
        if isinstance(member, discord.Member):
            await channel.set_permissions(member, overwrite=None)

    # Move the channel back to its previous category
    previous_category_data = archive_data.get('pre_cat', {})
    previous_category_id = previous_category_data.get('i')
    if previous_category_id:
        previous_category = interaction.guild.get_channel(previous_category_id)
        if previous_category and isinstance(previous_category, discord.CategoryChannel):
            await channel.edit(category=previous_category)
        else:
            await channel.edit(category=None)  # Move to no category
    else:
        await channel.edit(category=None)  # Move to no category

    await interaction.followup.send("Channel has been unarchived.", ephemeral=True)
    if admin_log_cog:
        await admin_log_cog.log_interaction(interaction=interaction,
                                            priority="info",
                                            text=f"Channel {channel.name} restored.")


async def setup(bot):
    await bot.add_cog(ArchiveCog(bot))
