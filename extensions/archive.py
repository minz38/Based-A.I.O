import re
import json
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
    async def archive(self, interaction: discord.Interaction, target_archive_category_id: str):
        logger.info(f"Command: {interaction.command.name} used by {interaction.user.name}")
        admin_log_cog = interaction.client.get_cog("AdminLog")

        # Defer the response to give the bot time to process
        await interaction.response.defer(ephemeral=True)  # noqa

        # Get the current channel
        channel = interaction.channel

        # Ensure the command is used in a text channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("This command can only be used in a text channel.", ephemeral=True)
            return

        # Validate and fetch the archive category
        try:
            category_id = int(target_archive_category_id)
            archive_category = interaction.guild.get_channel(category_id)
            if not isinstance(archive_category, discord.CategoryChannel):
                raise ValueError
        except ValueError:
            await interaction.followup.send("Invalid category ID provided.", ephemeral=True)
            return

        if admin_log_cog:
            await admin_log_cog.log_interaction(interaction=interaction,
                                                priority="warn",
                                                text=f"Channel {channel.name} will be archived to:"
                                                     f" {archive_category.name}.")

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

        # Prepare messages detailing permission changes
        def format_overwrite(overwrites):
            allow_perms, deny_perms = overwrites.pair()
            allow = [perm for perm in discord.Permissions.VALID_FLAGS if getattr(allow_perms, perm)]
            deny = [perm for perm in discord.Permissions.VALID_FLAGS if getattr(deny_perms, perm)]
            result = ''
            if allow:
                result += f"Allow: {', '.join(allow)}"
            if deny:
                if result:
                    result += "; "
                result += f"Deny: {', '.join(deny)}"
            return result or "No permissions set"

        previous_permissions_text = "\n".join(
            f"{escape_mentions(getattr(target, 'n', str(target)))}: {format_overwrite(overwrite)}"
            for target, overwrite in previous_overwrites.items()
        )

        new_overwrites = channel.overwrites
        new_permissions_text = "\n".join(
            f"{escape_mentions(getattr(target, 'n', str(target)))}: {format_overwrite(overwrite)}"
            for target, overwrite in new_overwrites.items()
        )

        previous_members_text = ", ".join(escape_mentions(member.name) for member in members_with_access)

        current_members_with_access = [
            member for member in channel.guild.members
            if channel.permissions_for(member).read_messages
        ]
        new_members_text = ", ".join(escape_mentions(member.name) for member in current_members_with_access)

        # Prepare data for restoring
        previous_permission_data = []
        for target, overwrite in previous_overwrites.items():
            target_data = {
                'i': target.id,
                't': 'r' if isinstance(target, discord.Role) else 'm',  # r role or m member
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
        # archive_message = (
        #     "This channel has been archived:\n\n"
        #     f"**Previous permission settings:**\n{previous_permissions_text}\n\n"
        #     f"**List of previous members in this channel:**\n{previous_members_text}\n\n"
        #     f"**New role permission settings:**\n{new_permissions_text}\n\n"
        #     f"**List of people who still have access:**\n{new_members_text}\n\n"
        #     f"```json\n{json.dumps(archive_data)}\n```"
        # )
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


@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
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

    if admin_log_cog:
        await admin_log_cog.log_interaction(interaction=interaction,
                                            priority="info",
                                            text=f"Channel {message.channel.name} restored.")
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


async def setup(bot):
    await bot.add_cog(ArchiveCog(bot))
