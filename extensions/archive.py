import discord
from discord.ext import commands
from discord import app_commands
import json
import re


class ArchiveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="archive", description="Archive the current channel")
    async def archive(self, interaction: discord.Interaction, target_archive_category_id: str):
        # Defer the response to give the bot time to process
        await interaction.response.defer(ephemeral=True)

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

        # Collect current permission settings and print them
        previous_overwrites = channel.overwrites.copy()
        print(f"Current permission overwrites for channel '{channel.name}':")
        for target, overwrite in previous_overwrites.items():
            print(f"{target}: {overwrite}")

        # Get members who can currently see the channel
        members_with_access = []
        for member in channel.guild.members:
            permissions = channel.permissions_for(member)
            if permissions.read_messages:
                members_with_access.append(member)

        # Save the previous category
        previous_category = channel.category

        # Remove role permissions and replace with per-user permissions
        for target in list(channel.overwrites):
            if isinstance(target, discord.Role):
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
            f"{getattr(target, 'name', str(target))}: {format_overwrite(overwrite)}"
            for target, overwrite in previous_overwrites.items()
        )

        new_overwrites = channel.overwrites
        new_permissions_text = "\n".join(
            f"{getattr(target, 'name', str(target))}: {format_overwrite(overwrite)}"
            for target, overwrite in new_overwrites.items()
        )

        previous_members_text = ", ".join(member.name for member in members_with_access)

        current_members_with_access = [
            member for member in channel.guild.members
            if channel.permissions_for(member).read_messages
        ]
        new_members_text = ", ".join(member.name for member in current_members_with_access)

        # Prepare data for unarchiving
        previous_permission_data = []
        for target, overwrite in previous_overwrites.items():
            target_data = {
                'id': target.id,
                'type': 'role' if isinstance(target, discord.Role) else 'member',
                'allow': overwrite.pair()[0].value,
                'deny': overwrite.pair()[1].value
            }
            previous_permission_data.append(target_data)

        # Include previous category info
        previous_category_data = {
            'id': previous_category.id if previous_category else None,
            'name': previous_category.name if previous_category else None
        }

        # Create a JSON object
        archive_data = {
            'previous_permissions': previous_permission_data,
            'previous_category': previous_category_data
        }

        # Send the archive message in the channel
        archive_message = (
            "This channel has been archived:\n\n"
            f"**Previous permission settings:**\n{previous_permissions_text}\n\n"
            f"**List of previous members in this channel:**\n{previous_members_text}\n\n"
            f"**New role permission settings:**\n{new_permissions_text}\n\n"
            f"**List of people who still have access:**\n{new_members_text}\n\n"
            f"```json\n{json.dumps(archive_data)}\n```"
        )
        await channel.send(archive_message)

        # Inform the user that the channel has been archived
        await interaction.followup.send("Channel has been archived.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ArchiveCog(bot))
