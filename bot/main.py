import discord
from discord.ext import commands
import os
import asyncio
import pathlib

from utils.database import Database
from utils.config_manager import ConfigManager


def _load_dotenv():
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        os.environ.setdefault(key, value)
    # Map DC_TOKEN to DISCORD_BOT_TOKEN
    dc_token = os.environ.get("DC_TOKEN")
    if dc_token and not os.environ.get("DISCORD_BOT_TOKEN"):
        os.environ["DISCORD_BOT_TOKEN"] = dc_token

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class TicketBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.db = Database()
        self.config_manager = ConfigManager()

    async def setup_hook(self):
        await self.db.connect()
        await self.load_extension("cogs.tickets")
        await self.load_extension("cogs.setup")
        await self.load_extension("cogs.moderation")
        await self.load_extension("cogs.stats")
        await self.load_extension("cogs.transcripts")
        await self.tree.sync()

    async def on_ready(self):
        if self.user:
            print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")

    async def close(self):
        await self.db.close()
        await super().close()

bot = TicketBot()

if __name__ == "__main__":
    _load_dotenv()
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is not set! Add DC_TOKEN to .env or set DISCORD_BOT_TOKEN.")
    bot.run(token)
