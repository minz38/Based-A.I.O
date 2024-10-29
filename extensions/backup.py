import re
import os
import json
import shutil
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from logger import LoggerManager

logger = LoggerManager(name="BackupManager", level="INFO", log_file="logs/BackupManager.log").get_logger()


class BackupManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Create a / backup command
    @app_commands.command(name='backup', description='Returns a backup file for roles, channel and user permission')
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.choices(create_backup=[app_commands.Choice(name="All", value='all'),
                                         app_commands.Choice(name="Roles", value='roles'),
                                         app_commands.Choice(name="Channels", value='channels'),
                                         app_commands.Choice(name="Users", value='users'),
                                         app_commands.Choice(name="Emojis", value='emojis'),
                                         app_commands.Choice(name="Stickers", value='sticker'),
                                         app_commands.Choice(name="Soundboard", value='soundboard'),
                                         app_commands.Choice(name="VRC Link Map", value='VRC link map')
                                         ])
    async def backup(self, interaction: discord.Interaction, create_backup: str) -> None:
        admin_log_cog = interaction.client.get_cog("AdminLog")
        if admin_log_cog:
            await admin_log_cog.log_interaction(interaction=interaction,
                                                priority="info",
                                                text=f"Backup started for: {create_backup}...")

        logger.info(f"Command: {interaction.command.name} with option: {create_backup} used by {interaction.user.name}")
        match create_backup:
            case 'all':
                await interaction.response.send_message(f"Starting full backup...")  # noqa
                await create_backup_all(interaction)

            case 'roles':
                await interaction.response.send_message(f"Starting roles backup...")  # noqa
                await create_role_backup(interaction)

            case 'channels':
                await interaction.response.send_message(f"Starting channels backup...")  # noqa
                await create_channel_backup(interaction)

            case 'users':
                await interaction.response.send_message(f"Starting users backup...")  # noqa
                await create_user_backup(interaction)

            case 'emojis':
                await interaction.response.send_message(f"Starting emojis backup...")  # noqa
                await create_emoji_backup(interaction)

            case 'sticker':
                await interaction.response.send_message(f"Starting sticker backup...")  # noqa
                await create_sticker_backup(interaction)

            case 'soundboard':
                await interaction.response.send_message(f"Starting soundboard backup...")  # noqa
                await create_soundboard_backup(interaction)

            case 'vrc link map':
                await interaction.response.send_message(f"Starting VRC link map backup...")  # noqa
                await create_vrc_link_map_backup(interaction)
            case _:
                await interaction.response.send_message(  # noqa
                    "Invalid backup option. Please choose one of the following:"
                    " All, Roles, Channels, Users, Emojis, Stickers, Soundboard, VRC Link Map"
                )


# Function to sanitize filenames
def sanitize_filename(filename):
    # Replace any invalid characters with an underscore
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


# Generic method to handle emoji and sticker backups
async def create_media_backup(interaction, media_type, media_items):
    timestamp = datetime.now().strftime("%d%m%Y")
    base_backup_file = f'backup_{media_type}s_{interaction.guild_id}_{timestamp}.zip"'
    backup_dir = os.path.join("backup", base_backup_file)
    zip_file_path = f"{backup_dir}.zip"

    try:
        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)

        # Initialize metadata list
        media_metadata = []

        async with aiohttp.ClientSession() as session:
            for item in media_items:
                media_info = {
                    'id': item.id,
                    'name': item.name,
                    'url': str(item.url)
                }

                if media_type == 'emoji':
                    media_info['animated'] = item.animated

                media_metadata.append(media_info)

                # Sanitize the filename
                sanitized_name = sanitize_filename(item.name)

                # Download the media file
                async with session.get(item.url) as response:
                    if response.status == 200:
                        file_path = os.path.join(backup_dir,
                                                 f"{sanitized_name}.png" if media_type == 'emoji'
                                                 else f"{sanitized_name}.webp")
                        with open(file_path, 'wb') as f:
                            f.write(await response.read())

        # Save metadata to JSON
        with open(os.path.join(backup_dir, f"{media_type}_metadata.json"), 'w') as f:
            json.dump(media_metadata, f, indent=4)

        # Create a ZIP file
        shutil.make_archive(backup_dir, 'zip', backup_dir)

        # Send the ZIP file as a response
        file = discord.File(zip_file_path, filename=f"{base_backup_file}.zip")
        await interaction.followup.send(f"{media_type.capitalize()} backup created successfully:", file=file)

    except Exception as e:
        await interaction.followup.send(f"Error creating {media_type} backup: {e}")

    finally:
        # Clean up the backup directory after zipping
        shutil.rmtree(backup_dir, ignore_errors=True)


async def create_emoji_backup(interaction):
    await create_media_backup(interaction, 'emoji', interaction.guild.emojis)


async def create_sticker_backup(interaction):
    await create_media_backup(interaction, 'sticker', interaction.guild.stickers)


async def create_soundboard_backup(interaction):
    await interaction.followup.send("Discord.py does not provide a way to back up soundboards,"
                                    " so this command is currently disabled.")
    # soundboard_items = interaction.guild.soundboard_sounds()

    # # Check if there are any soundboard sounds to back up
    # if not soundboard_items:
    #     await interaction.followup.send("No soundboard sounds found to back up.")
    #     return
    #
    # timestamp = datetime.now().strftime("%d%m%Y")
    # base_backup_file = f"backup_soundboards_{interaction.guild_id}_{timestamp}"
    # backup_dir = os.path.join("backup", base_backup_file)
    # zip_file_path = f"{backup_dir}.zip"
    #
    # try:
    #     # Create backup directory
    #     os.makedirs(backup_dir, exist_ok=True)
    #
    #     # Initialize metadata list
    #     soundboard_metadata = []
    #
    #     async with aiohttp.ClientSession() as session:
    #         for sound in soundboard_items:
    #             sound_info = {
    #                 'id': sound.id,
    #                 'name': sound.name,
    #                 'url': str(sound.url)
    #             }
    #
    #             soundboard_metadata.append(sound_info)
    #
    #             # Sanitize the filename
    #             sanitized_name = sanitize_filename(sound.name)
    #
    #             # Download the sound file
    #             async with session.get(sound.url) as response:
    #                 if response.status == 200:
    #                     file_path = os.path.join(backup_dir,
    #                                              f"{sanitized_name}.mp3")  # Assuming sound files are in .mp3 format
    #                     with open(file_path, 'wb') as f:
    #                         f.write(await response.read())
    #
    #     # Save metadata to JSON
    #     with open(os.path.join(backup_dir, "soundboard_metadata.json"), 'w') as f:
    #         json.dump(soundboard_metadata, f, indent=4)
    #
    #     # Create a ZIP file
    #     shutil.make_archive(backup_dir, 'zip', backup_dir)
    #
    #     # Send the ZIP file as a response
    #     file = discord.File(zip_file_path, filename=f"{base_backup_file}.zip")
    #     await interaction.followup.send("Soundboard backup created successfully.", file=file)
    #
    # except Exception as e:
    #     await interaction.followup.send(f"Error creating soundboard backup: {e}")
    #
    # finally:
    #     # Clean up the backup directory after zipping
    #     shutil.rmtree(backup_dir, ignore_errors=True)


async def create_vrc_link_map_backup(interaction):
    # Define the source path for the VRChat link map file
    source_file = 'data/vrc/vrchat_user_link_map.json'

    # Ensure the source file exists before attempting to back it up
    if not os.path.exists(source_file):
        await interaction.followup.send(f"VRChat link map file not found.")
        return

    # Define the backup path with a timestamp
    # guild_id = interaction.guild_id
    timestamp = datetime.now().strftime("%d%m%Y")
    base_backup_file = f"backup_vrc_link_map_{interaction.guild_id}_{timestamp}.json"
    counter = 1
    backup_file = f"{base_backup_file}.json"
    backup_path = os.path.join("backup", backup_file)

    # Increment the counter until a unique filename is found
    while os.path.exists(backup_path):
        backup_file = f"{base_backup_file}_{counter}.json"
        backup_path = os.path.join("backup", backup_file)
        counter += 1

    try:
        # Create directory if it doesn't exist
        os.makedirs("backup", exist_ok=True)

        # Copy the file to the backup location
        with open(source_file, 'r') as src:
            data = json.load(src)
            with open(backup_path, 'w') as dst:
                json.dump(data, dst, indent=4)

        # Send a confirmation message
        file = discord.File(backup_path, filename=backup_file)
        await interaction.followup.send(f"VRChat link map backup created successfully.", file=file)

    except Exception as e:
        await interaction.followup.send(f"Error creating VRChat link map backup: {e}")
        return


async def create_role_backup(interaction):
    timestamp = datetime.now().strftime("%d%m%Y")
    base_backup_file = f"backup_roles_{interaction.guild_id}_{timestamp}"
    counter = 1
    backup_file = f"{base_backup_file}.json"
    backup_path = os.path.join("backup", backup_file)

    # Increment the counter until a unique filename is found
    while os.path.exists(backup_path):
        backup_file = f"{base_backup_file}_{counter}.json"
        backup_path = os.path.join("backup", backup_file)
        counter += 1

    try:
        # Create directory if it doesn't exist
        os.makedirs("backup", exist_ok=True)

        # Collect all roles and their permissions
        all_roles_data = []
        for role in interaction.guild.roles:
            role_data = {
                'id': role.id,
                'name': role.name,
                'is_bot_managed': role.is_bot_managed(),
                'is_default': role.is_default(),
                'is_premium_subscriber': role.is_premium_subscriber(),
                'position': role.position,
                'mentionable': role.mentionable,
                'permissions': role.permissions.value,
                'hoist': role.hoist,
                'members': [member.id for member in role.members],
                'member_names': [member.name for member in role.members]
            }
            all_roles_data.append(role_data)

        # Sort the roles from the highest position to lowest
        all_roles_data.sort(key=lambda x: x['position'], reverse=True)

        # Save data to JSON file
        with open(backup_path, 'w') as f:
            json.dump({'roles': all_roles_data}, f, indent=4)

        # Send the file in the response
        file = discord.File(backup_path, filename=backup_file)
        await interaction.followup.send(f"Backup created successfully:", file=file)
    except Exception as e:
        await interaction.followup.send(f"Error creating backup: {e}")
        return


async def create_channel_backup(interaction):
    # guild_id = interaction.guild_id
    timestamp = datetime.now().strftime("%d%m%Y")
    base_backup_file = f"backup_channels_{interaction.guild_id}_{timestamp}"
    counter = 1
    backup_file = f"{base_backup_file}.json"
    backup_path = os.path.join("backup", backup_file)

    # Increment the counter until a unique filename is found
    while os.path.exists(backup_path):
        backup_file = f"{base_backup_file}_{counter}.json"
        backup_path = os.path.join("backup", backup_file)
        counter += 1

    try:
        # Create directory if it doesn't exist
        os.makedirs("backup", exist_ok=True)

        # Collect all channels and their permissions, descriptions, and webhooks
        all_channels_data = []
        for channel in interaction.guild.channels:
            channel_data = {
                'id': channel.id,
                'name': channel.name,
                'type': str(channel.type),
                'position': channel.position,
                'category': channel.category.name if channel.category else None,
                'description': channel.topic if isinstance(channel, discord.TextChannel) else None,
                'permissions': [],
                'webhooks': []
            }

            # Collect permissions for each role in the channel
            for role, perms in channel.overwrites.items():
                channel_data['permissions'].append({
                    'role': role.name,
                    'allow': perms.pair()[0].value,
                    'deny': perms.pair()[1].value
                })

            # Collect webhooks for the channel, only if the channel supports them
            if isinstance(channel, discord.TextChannel):  # Generalize to TextChannel type
                webhooks = await channel.webhooks()
                for webhook in webhooks:
                    channel_data['webhooks'].append({
                        'id': webhook.id,
                        'name': webhook.name,
                        'url': webhook.url,
                        'type': str(webhook.type),
                        'created_at': webhook.created_at.strftime("%d/%m/%Y %H:%M:%S"),
                        'channel_id': webhook.channel_id
                    })

            all_channels_data.append(channel_data)

        # Sort the channels from the highest position to lowest
        all_channels_data.sort(key=lambda x: x['position'], reverse=True)

        # Save data to JSON file
        with open(backup_path, 'w') as f:
            json.dump({'channels': all_channels_data}, f, indent=4)

        # Send the file in the response
        file = discord.File(backup_path, filename=backup_file)
        await interaction.followup.send(f"Backup created successfully:", file=file)
    except Exception as e:
        await interaction.followup.send(f"Error creating backup: {e}")
        return


async def create_user_backup(interaction):
    # guild_id = interaction.guild_id
    timestamp = datetime.now().strftime("%d%m%Y")
    base_backup_file = f"backup_users_{interaction.guild_id}_{timestamp}"
    counter = 1
    backup_file = f"{base_backup_file}.json"
    backup_path = os.path.join("backup", backup_file)

    # Increment the counter until a unique filename is found
    while os.path.exists(backup_path):
        backup_file = f"{base_backup_file}_{counter}.json"
        backup_path = os.path.join("backup", backup_file)
        counter += 1

    try:
        # Create directory if it doesn't exist
        os.makedirs("backup", exist_ok=True)

        # Collect all members (including bots)
        all_users_data = []
        for member in interaction.guild.members:
            accessible_channels = []

            for channel in interaction.guild.channels:
                if channel.permissions_for(member).read_messages:
                    accessible_channels.append({
                        'channel_id': channel.id,
                        'channel_name': channel.name
                    })

            user_data = {
                'id': member.id,
                'name': member.name,
                'discriminator': member.discriminator,
                'is_bot': member.bot,
                'roles': [role.name for role in member.roles],
                'joined_at': member.joined_at.strftime("%d/%m/%Y %H:%M:%S"),
                'accessible_channels': accessible_channels
            }
            all_users_data.append(user_data)

        # Save data to JSON file
        with open(backup_path, 'w') as f:
            json.dump({'users': all_users_data}, f, indent=4)

        # Send the file in the response
        file = discord.File(backup_path, filename=backup_file)
        await interaction.followup.send(f"Backup created successfully:", file=file)
    except Exception as e:
        await interaction.followup.send(f"Error creating backup: {e}")
        return


async def create_backup_all(interaction):
    await create_role_backup(interaction)
    await create_channel_backup(interaction)
    await create_user_backup(interaction)
    await create_vrc_link_map_backup(interaction)


async def setup(bot):
    await bot.add_cog(BackupManager(bot))
