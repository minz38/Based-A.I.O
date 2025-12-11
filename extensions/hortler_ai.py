import os
import json
import aiohttp
import discord
from typing import Optional, List, Dict
from discord.ext import commands
from discord import app_commands
from logger import LoggerManager

logger = LoggerManager(name="Hortler AI", level="INFO", log_file="logs/hortler_ai.log").get_logger()


class HortlerAI(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.ollama_url = os.getenv("OLLAMA_URL", "http://144.76.183.169:11434").rstrip("/")

        # In-memory chat history: {channel_id: [{"role": "...", "content": "..."}]}
        self.chat_histories: Dict[int, List[Dict[str, str]]] = {}

        # Configuration cache: {guild_id: config_dict}
        self.guild_configs: Dict[int, Dict] = {}

    # -------------------------------------------------------------------------
    # Configuration Helper Methods
    # -------------------------------------------------------------------------

    @staticmethod
    def _get_config_path(guild_id: int) -> str:
        return f"configs/guilds/{guild_id}.json"

    def _get_default_config(self) -> Dict:
        return {
            "enabled": False,
            "model": None,
            "channel_id": None,
            "system_prompt": "You are a helpful assistant.",
            "temperature": 0.7,
            "memory_limit": 20
        }

    def _load_guild_config(self, guild_id: int) -> Dict:
        """Load guild config and extract hortler_ai settings."""
        if guild_id in self.guild_configs:
            return self.guild_configs[guild_id]

        config_path = self._get_config_path(guild_id)
        default_config = self._get_default_config()

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    guild_data = json.load(f)
                    ai_config = guild_data.get("hortler_ai", default_config)
                    # Merge with defaults to ensure all keys exist
                    merged_config = {**default_config, **ai_config}
                    self.guild_configs[guild_id] = merged_config
                    return merged_config
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading config for guild {guild_id}: {e}")

        self.guild_configs[guild_id] = default_config
        return default_config

    def _save_guild_config(self, guild_id: int, ai_config: Dict) -> None:
        """Save hortler_ai config to guild JSON file."""
        config_path = self._get_config_path(guild_id)

        # Load existing guild data or create new
        guild_data = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    guild_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error reading config for guild {guild_id}: {e}")

        guild_data["hortler_ai"] = ai_config
        self.guild_configs[guild_id] = ai_config

        # Ensure directory exists
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(guild_data, f, indent=4)
        except IOError as e:
            logger.error(f"Error saving config for guild {guild_id}: {e}")

    # -------------------------------------------------------------------------
    # Ollama API Helper Methods
    # -------------------------------------------------------------------------

    async def _fetch_models(self) -> List[str]:
        """Fetch available models from Ollama server."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.ollama_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = data.get("models", [])
                        return [model["name"] for model in models]
                    else:
                        logger.error(f"Failed to fetch models: HTTP {response.status}")
                        return []
        except aiohttp.ClientError as e:
            logger.error(f"Error connecting to Ollama server: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching models: {e}")
            return []

    async def _send_chat_request(
        self,
        model: str,
        messages: List[Dict],
        temperature: float
    ) -> Optional[str]:
        """Send chat request to Ollama and return the response."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("message", {}).get("content", "")
                    else:
                        error_text = await response.text()
                        logger.error(f"Ollama chat error: HTTP {response.status} - {error_text}")
                        return None
        except aiohttp.ClientError as e:
            logger.error(f"Error sending chat request: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in chat request: {e}")
            return None

    # -------------------------------------------------------------------------
    # Model Autocomplete
    # -------------------------------------------------------------------------

    async def model_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for model selection."""
        models = await self._fetch_models()
        filtered = [m for m in models if current.lower() in m.lower()][:25]
        return [app_commands.Choice(name=m, value=m) for m in filtered]

    # -------------------------------------------------------------------------
    # Command Group: /ai_setup
    # -------------------------------------------------------------------------

    ai_setup_group = app_commands.Group(
        name="ai_setup",
        description="Configure the Hortler AI settings."
    )

    @ai_setup_group.command(name="model", description="Select the Ollama model to use.")
    @app_commands.describe(model="The model to use for AI responses")
    @app_commands.autocomplete(model=model_autocomplete)
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def setup_model(self, interaction: discord.Interaction, model: str) -> None:
        config = self._load_guild_config(interaction.guild_id)
        config["model"] = model
        self._save_guild_config(interaction.guild_id, config)

        await interaction.response.send_message(f"AI model set to: **{model}**", ephemeral=True)
        logger.info(f"Guild {interaction.guild_id}: Model set to {model}")

    @ai_setup_group.command(name="channel", description="Set the channel where AI responds to messages.")
    @app_commands.describe(channel="The channel for AI chat")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def setup_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        config = self._load_guild_config(interaction.guild_id)
        config["channel_id"] = channel.id
        self._save_guild_config(interaction.guild_id, config)

        await interaction.response.send_message(f"AI chat channel set to: {channel.mention}", ephemeral=True)
        logger.info(f"Guild {interaction.guild_id}: Channel set to {channel.id}")

    @ai_setup_group.command(name="systemprompt", description="Set the system prompt for the AI.")
    @app_commands.describe(prompt="The system prompt to use")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def setup_systemprompt(self, interaction: discord.Interaction, prompt: str) -> None:
        config = self._load_guild_config(interaction.guild_id)
        config["system_prompt"] = prompt
        self._save_guild_config(interaction.guild_id, config)

        await interaction.response.send_message("System prompt updated.", ephemeral=True)
        logger.info(f"Guild {interaction.guild_id}: System prompt updated")

    @ai_setup_group.command(name="temperature", description="Set the AI temperature (creativity).")
    @app_commands.describe(temperature="Temperature value (0.0-2.0)")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def setup_temperature(self, interaction: discord.Interaction, temperature: float) -> None:
        if not 0.0 <= temperature <= 2.0:
            await interaction.response.send_message(
                "Temperature must be between 0.0 and 2.0",
                ephemeral=True
            )
            return

        config = self._load_guild_config(interaction.guild_id)
        config["temperature"] = temperature
        self._save_guild_config(interaction.guild_id, config)

        await interaction.response.send_message(f"Temperature set to: **{temperature}**", ephemeral=True)
        logger.info(f"Guild {interaction.guild_id}: Temperature set to {temperature}")

    @ai_setup_group.command(name="memory_limit", description="Set the max messages to remember.")
    @app_commands.describe(limit="Maximum number of messages to remember (1-100)")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def setup_memory_limit(self, interaction: discord.Interaction, limit: int) -> None:
        if not 1 <= limit <= 100:
            await interaction.response.send_message(
                "Memory limit must be between 1 and 100",
                ephemeral=True
            )
            return

        config = self._load_guild_config(interaction.guild_id)
        config["memory_limit"] = limit
        self._save_guild_config(interaction.guild_id, config)

        await interaction.response.send_message(f"Memory limit set to: **{limit}** messages", ephemeral=True)
        logger.info(f"Guild {interaction.guild_id}: Memory limit set to {limit}")

    # -------------------------------------------------------------------------
    # Standalone Commands
    # -------------------------------------------------------------------------

    @app_commands.command(name="ai_enable", description="Enable the AI chat feature.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def ai_enable(self, interaction: discord.Interaction) -> None:
        config = self._load_guild_config(interaction.guild_id)

        # Validate required settings
        if not config.get("model"):
            await interaction.response.send_message(
                "Please set a model first using `/ai_setup model`",
                ephemeral=True
            )
            return
        if not config.get("channel_id"):
            await interaction.response.send_message(
                "Please set a channel first using `/ai_setup channel`",
                ephemeral=True
            )
            return

        config["enabled"] = True
        self._save_guild_config(interaction.guild_id, config)

        channel = self.bot.get_channel(config["channel_id"])
        channel_mention = channel.mention if channel else f"<#{config['channel_id']}>"

        await interaction.response.send_message(f"AI chat enabled in {channel_mention}", ephemeral=True)
        logger.info(f"Guild {interaction.guild_id}: AI enabled")

    @app_commands.command(name="ai_disable", description="Disable the AI chat feature.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def ai_disable(self, interaction: discord.Interaction) -> None:
        config = self._load_guild_config(interaction.guild_id)
        config["enabled"] = False
        self._save_guild_config(interaction.guild_id, config)

        await interaction.response.send_message("AI chat disabled.", ephemeral=True)
        logger.info(f"Guild {interaction.guild_id}: AI disabled")

    @app_commands.command(name="ai_status", description="Show current AI configuration.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def ai_status(self, interaction: discord.Interaction) -> None:
        config = self._load_guild_config(interaction.guild_id)

        channel = self.bot.get_channel(config.get("channel_id")) if config.get("channel_id") else None
        channel_str = channel.mention if channel else "Not set"

        system_prompt = config.get("system_prompt", "Not set")
        if len(system_prompt) > 100:
            system_prompt = system_prompt[:100] + "..."

        embed = discord.Embed(title="Hortler AI Configuration", color=discord.Color.blue())
        embed.add_field(name="Status", value="Enabled" if config.get("enabled") else "Disabled", inline=True)
        embed.add_field(name="Model", value=config.get("model") or "Not set", inline=True)
        embed.add_field(name="Channel", value=channel_str, inline=True)
        embed.add_field(name="Temperature", value=str(config.get("temperature", 0.7)), inline=True)
        embed.add_field(name="Memory Limit", value=str(config.get("memory_limit", 20)), inline=True)
        embed.add_field(name="System Prompt", value=system_prompt, inline=False)

        # Show chat history size for the configured channel
        channel_id = config.get("channel_id")
        if channel_id and channel_id in self.chat_histories:
            history_size = len(self.chat_histories[channel_id])
            embed.add_field(name="Current History", value=f"{history_size} messages", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ai_clear_history", description="Clear the AI chat history.")
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    async def ai_clear_history(self, interaction: discord.Interaction) -> None:
        config = self._load_guild_config(interaction.guild_id)
        channel_id = config.get("channel_id")

        if channel_id and channel_id in self.chat_histories:
            del self.chat_histories[channel_id]
            await interaction.response.send_message("Chat history cleared.", ephemeral=True)
            logger.info(f"Guild {interaction.guild_id}: Chat history cleared for channel {channel_id}")
        else:
            await interaction.response.send_message("No chat history to clear.", ephemeral=True)

    # -------------------------------------------------------------------------
    # Message Event Handler
    # -------------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignore bot messages
        if message.author.bot:
            return

        # Ignore DMs
        if not message.guild:
            return

        # Load config
        config = self._load_guild_config(message.guild.id)

        # Check if enabled and in correct channel
        if not config.get("enabled"):
            return
        if message.channel.id != config.get("channel_id"):
            return

        # Only process text content (ignore if message is empty/only attachments)
        if not message.content.strip():
            return

        # Ignore pinned messages (allows channel rules to be pinned without AI responding)
        if message.pinned:
            return

        # Get settings
        model = config.get("model")
        system_prompt = config.get("system_prompt", "You are a helpful assistant.")
        temperature = config.get("temperature", 0.7)
        memory_limit = config.get("memory_limit", 20)

        if not model:
            logger.warning(f"Guild {message.guild.id}: No model configured")
            return

        # Initialize channel history if not exists
        if message.channel.id not in self.chat_histories:
            self.chat_histories[message.channel.id] = []

        history = self.chat_histories[message.channel.id]

        # Format user message with username
        user_message = f"{message.author.display_name}: {message.content}"
        history.append({"role": "user", "content": user_message})

        # Trim history to memory limit
        if len(history) > memory_limit:
            history = history[-memory_limit:]
            self.chat_histories[message.channel.id] = history

        # Build messages list with system prompt
        messages = [{"role": "system", "content": system_prompt}] + history

        # Show typing indicator
        async with message.channel.typing():
            response = await self._send_chat_request(model, messages, temperature)

        if response:
            # Add assistant response to history
            history.append({"role": "assistant", "content": response})

            # Trim again after adding response
            if len(history) > memory_limit:
                self.chat_histories[message.channel.id] = history[-memory_limit:]

            # Send response (handle Discord message length limit)
            if len(response) <= 2000:
                await message.channel.send(response)
            else:
                # Split into chunks
                chunks = [response[i:i+2000] for i in range(0, len(response), 2000)]
                for chunk in chunks:
                    await message.channel.send(chunk)
        else:
            await message.channel.send("Sorry, I encountered an error processing your request.")
            logger.error(f"Guild {message.guild.id}: Failed to get response from Ollama")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HortlerAI(bot))
