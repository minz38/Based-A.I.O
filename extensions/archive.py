import json
import os
import discord
from discord.ext import commands
from discord import app_commands
from bot import bot as shadow_bot
from logger import LoggerManager
import dependencies.encryption_handler as encryption_handler
import shutil  # For removing directories

logger = LoggerManager(name="Archive", level="INFO", log_file="logs/Archive.log").get_logger()

key: bytes = encryption_handler.load_key_from_config()  # Load the encryption key from config


class ConfirmArchiveView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, archive_func):
        super().__init__(timeout=180)
        self.interaction = interaction
        self.archive_func = archive_func

    @discord.ui.button(label="Proceed", style=discord.ButtonStyle.green, emoji='✅')
    async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):  # noqa
        if interaction.user != self.interaction.user:
            await interaction.response.send_message("You are not authorized to perform this action.",
                                                    ephemeral=True)
            return
        await interaction.response.defer()  # noqa
        await self.archive_func()
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji='✖️')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):  # noqa
        if interaction.user != self.interaction.user:
            await interaction.response.send_message("You are not authorized to perform this action.",
                                                    ephemeral=True)
            return
        await interaction.response.send_message("Archiving has been canceled.", ephemeral=True)
        self.stop()


class ArchiveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="archive", description="Archive the current channel")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def archive(self, interaction: discord.Interaction):
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
            await admin_log_cog.log_interaction(
                interaction=interaction,
                priority="warn",
                text=f"Channel {channel.name} will be archived to: {archive_category.name}."
            )

        # Confirmation message
        confirmation_message = (
            f"📦 **Archive Channel**\n"
            f"**ADMINISTRATOR PERMISSIONS REQUIRED**\n"
            f"Archiving this channel will **bake all permissions of roles and users into the channel** "
            f"and then move it to the archive category.\n\n"
            f"Do you want to proceed?"
        )

        # Define the archive function to be called upon confirmation
        async def proceed_with_archiving():
            # Collect current permission settings and log them
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

            # Identify members with existing per-user overwrites
            previous_member_overwrites = [
                target.id for target in previous_overwrites if isinstance(target, discord.Member)
            ]

            # Remove role permissions (except @everyone) and replace with per-user permissions
            for target in list(channel.overwrites):
                if isinstance(target, discord.Role) and target != channel.guild.default_role:  # ignore @everyone
                    await channel.set_permissions(target, overwrite=None)

            # Explicitly deny @everyone from seeing the channel
            await channel.set_permissions(channel.guild.default_role, read_messages=False)

            # Store IDs of members who were granted temporary overwrites
            temp_member_overwrites = []

            # Grant read and send permissions to users who had access
            for member in members_with_access:
                await channel.set_permissions(
                    member,
                    overwrite=discord.PermissionOverwrite(
                        read_messages=True, send_messages=True
                    )
                )
                if member.id not in previous_member_overwrites:
                    temp_member_overwrites.append(member.id)

            # Move the channel to the archive category
            await channel.edit(category=archive_category)

            # Prepare data for restoring
            previous_permission_data = []
            for target, overwrite in previous_overwrites.items():
                target_data = {
                    'i': target.id,
                    't': 'r' if isinstance(target, discord.Role) else 'm',
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
                'pre_cat': previous_category_data,
                't_m_o': temp_member_overwrites
            }
            restore_data_str: str = json.dumps(archive_data, indent=4)
            logger.debug(f"X Restoring data: {restore_data_str}")

            # Encrypt the archive data
            encrypted_data: str = encryption_handler.encrypt(restore_data_str, key=key)
            logger.debug(f"X Encrypted data: {encrypted_data}")

            # Ensure the temp/archive directory exists
            os.makedirs("temp/archive", exist_ok=True)
            file_path = "temp/archive/restore.bin"  # Changed extension to .bin

            # Write the encrypted data to a file
            with open(file_path, 'w') as f:
                f.write(encrypted_data)

            # Send the file with .bin extension
            file: discord.File = discord.File(file_path, filename="restore.bin")
            await channel.send(
                "The channel has been archived.\n"
                "The channel is still accessible to users who once had access to it.\n"
                "*restore file:*",
                file=file
            )

            # Remove the archive directory (leave temp)
            shutil.rmtree("temp/archive", ignore_errors=True)
            logger.debug(f"X Temporary archive directory removed.")

            if admin_log_cog:
                await admin_log_cog.log_interaction(interaction=interaction,
                                                    priority="info",
                                                    text=f"Channel {channel.name} archived.")
            await interaction.followup.send("Channel has been archived.\n",
                                            ephemeral=True)

        # Create the confirmation view
        view = ConfirmArchiveView(interaction, proceed_with_archiving)

        # Send the confirmation message with the view
        await interaction.followup.send(content=confirmation_message, ephemeral=True, view=view)

    @app_commands.command(name="set_archive", description="Set the archive category for this guild")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_archive(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        admin_log_cog = interaction.client.get_cog("AdminLog")
        if admin_log_cog:
            await admin_log_cog.log_interaction(
                interaction=interaction,
                priority="info",
                text=f"Set archive category for guild {interaction.guild.name} to {category.name}."
            )
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

        await interaction.response.send_message(f"Archive category set to {category.name}.", ephemeral=True)
        logger.info(f"Archive category set to {category.name} ({category.id}) for guild {interaction.guild.name}")


@shadow_bot.tree.context_menu(name="Restore Channel")
@app_commands.allowed_installs(guilds=True, users=False)
@app_commands.guild_only()
async def restore_channel(interaction: discord.Interaction, message: discord.Message) -> None:
    logger.info(f"Command: {interaction.command.name} used by {interaction.user.name} on message id: {message.id}")
    admin_log_cog = interaction.client.get_cog("AdminLog")

    # Defer the response
    await interaction.response.defer(ephemeral=True)  # noqa

    # Ensure the message is from the bot and contains the archive data as an attachment
    if message.author != shadow_bot.user:
        await interaction.followup.send("This message was not sent by the bot.", ephemeral=True)
        return

    # Ensure the message is in a text channel
    channel = message.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send("This command can only be used in a text channel.", ephemeral=True)
        return

    # Look for restore.bin attachment and decrypt it
    archive_data = None
    for attachment in message.attachments:
        if attachment.filename == "restore.bin":
            encrypted_data = await attachment.read()
            restore_data = encrypted_data.decode('utf-8')  # decode from bytes to string
            try:
                data_str: str = encryption_handler.decrypt(restore_data)
                archive_data = json.loads(data_str)
            except Exception:
                await interaction.followup.send("Failed to decrypt or parse the restore data.", ephemeral=True)
                return
            break

    if archive_data is None:
        await interaction.followup.send("No valid restore.bin file found in the message attachments.", ephemeral=True)
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

    # Remove per-user permissions set during archiving that were not originally there
    temp_member_overwrites = archive_data.get('t_m_o', [])
    members_with_preexisting_overwrites = {perm_data.get('i') for perm_data in previous_permissions if
                                           perm_data.get('t') == 'm'}

    for member_id in temp_member_overwrites:
        if member_id in members_with_preexisting_overwrites:
            continue  # Skip removing overwrite for this member
        member = interaction.guild.get_member(member_id)
        if member:
            # Remove the temporary overwrite
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
