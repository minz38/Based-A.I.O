import os
import discord
from discord import app_commands
from discord.ext import commands
from logger import LoggerManager
from dependencies.audit_logger import log_interaction

logger = LoggerManager(name="Moderation", level="INFO", log_file="logs/mod.log").get_logger()

# Load environment variables safely
_member_env = os.getenv("MEMBER_ROLE_ID")
_guest_env = os.getenv("GUEST_ROLE_ID")

MEMBER_ROLE_ID: int | None = int(_member_env) if _member_env else None
GUEST_ROLE_ID: int | None = int(_guest_env) if _guest_env else None


@app_commands.context_menu(name="Make Member")
async def set_member_role(interaction: discord.Interaction, user: discord.User):
    """Assigns the 'Member' role to a user and removes 'Guest' role if they have it."""
    guild: discord.Guild = interaction.guild

    if not guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    member = guild.get_member(user.id)
    if not member:
        await interaction.response.send_message("User is not a member of this server.", ephemeral=True)
        return

    if MEMBER_ROLE_ID is None or GUEST_ROLE_ID is None:
        await interaction.response.send_message("Role IDs are not configured.", ephemeral=True)
        return

    member_role = guild.get_role(MEMBER_ROLE_ID)
    guest_role = guild.get_role(GUEST_ROLE_ID)

    if not member_role:
        await interaction.response.send_message("The 'Member' role was not found.", ephemeral=True)
        return

    if member_role in member.roles:
        await interaction.response.send_message(f"{member.mention} already has the 'Member' role.", ephemeral=True)
        return

    try:
        roles_to_add = [member_role]
        roles_to_remove = [guest_role] if guest_role in member.roles else []

        await member.add_roles(*roles_to_add, reason=f"Role assigned by {interaction.user}")
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=f"Role removed by {interaction.user}")

        await interaction.response.send_message(f"✅ {member.mention} is now a **Member**.", ephemeral=True)
        logger.info(f"{interaction.user} Assigned 'Member' role to {member}, removed 'Newcomer' role if present.")
        await log_interaction(interaction, "mod", reason="Role assignment")

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to assign roles.", ephemeral=True)
        logger.error("Bot lacks permissions to assign roles.")

    except discord.HTTPException as e:
        await interaction.response.send_message("❌ An error occurred while assigning the role.", ephemeral=True)
        logger.error(f"Failed to assign role: {e}")


@app_commands.context_menu(name="Make Newcomer")
async def set_guest_role(interaction: discord.Interaction, user: discord.User):
    """Assigns the 'Guest' role to a user and removes 'Member' role if they have it."""
    guild = interaction.guild

    if not guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    member = guild.get_member(user.id)
    if not member:
        await interaction.response.send_message("User is not a member of this server.", ephemeral=True)
        return

    if MEMBER_ROLE_ID is None or GUEST_ROLE_ID is None:
        await interaction.response.send_message("Role IDs are not configured.", ephemeral=True)
        return

    guest_role = guild.get_role(GUEST_ROLE_ID)
    member_role = guild.get_role(MEMBER_ROLE_ID)

    if not guest_role:
        await interaction.response.send_message("The 'Newcomer' role was not found.", ephemeral=True)
        return

    if guest_role in member.roles:
        await interaction.response.send_message(f"{member.mention} already has the 'Newcomer' role.", ephemeral=True)
        return

    try:
        roles_to_add = [guest_role]
        roles_to_remove = [member_role] if member_role in member.roles else []

        await member.add_roles(*roles_to_add, reason=f"Role assigned by {interaction.user}")
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove, reason=f"Role removed by {interaction.user}")

        await interaction.response.send_message(f"✅ {member.mention} is now a **Newcomer**.", ephemeral=True)
        logger.info(f"{interaction.user} Assigned 'Newcomer' role to {member}, removed 'Member' role if present.")
        await log_interaction(interaction, "mod", reason="Role assignment")

    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to assign roles.", ephemeral=True)
        logger.error("Bot lacks permissions to assign roles.")

    except discord.HTTPException as e:
        await interaction.response.send_message("❌ An error occurred while assigning the role.", ephemeral=True)
        logger.error(f"Failed to assign role: {e}")


async def setup(bot: commands.Bot) -> None:
    """Register role management context menus with the provided bot."""
    bot.tree.add_command(set_member_role)
    bot.tree.add_command(set_guest_role)
