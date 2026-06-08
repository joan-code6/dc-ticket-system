import io
import json
import asyncio
import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from main import TicketBot

_log = logging.getLogger(__name__)

SETUP_BYPASS_ROLE = 1314666319035240579


def _has_debug_access():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild:
            if interaction.user.guild_permissions.administrator:
                return True
            if interaction.user.get_role(SETUP_BYPASS_ROLE):
                return True
            raise app_commands.MissingPermissions(["Administrator"])

        for guild in interaction.client.guilds:
            member = guild.get_member(interaction.user.id)
            if member:
                if member.guild_permissions.administrator:
                    return True
                if member.get_role(SETUP_BYPASS_ROLE):
                    return True

        raise app_commands.CheckFailure("You don't have permission to use debug commands.")

    return app_commands.check(predicate)


class DebugCog(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot

    async def cog_load(self):
        _log.info("DebugCog loaded, registered commands: %s", [c.qualified_name for c in self.bot.tree.walk_commands() if 'debug' in c.qualified_name])

    debug_group = app_commands.Group(name="debug", description="Debug utilities")

    @debug_group.command(name="copy-config", description="Send the current config.json as a downloadable file")
    async def debug_copy_config(self, interaction: discord.Interaction):
        config_json = json.dumps(self.bot.config_manager.config, indent=2)
        file = discord.File(io.BytesIO(config_json.encode()), filename="config.json")
        await interaction.response.send_message(
            "Here's the current config:",
            file=file,
            ephemeral=True,
        )

    @debug_group.command(name="paste-config", description="Replace the config by pasting JSON in this DM")
    async def debug_paste_config(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.DMChannel):
            await interaction.response.send_message(
                "This command can only be used in DMs with the bot.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "Please paste the new config JSON in this DM now. You have 120 seconds.",
            ephemeral=True,
        )

        def check(m: discord.Message) -> bool:
            return m.author == interaction.user and m.channel == interaction.channel

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120.0)
        except asyncio.TimeoutError:
            await interaction.followup.send("Timed out. Please run the command again.", ephemeral=True)
            return

        try:
            new_config = json.loads(msg.content)
        except json.JSONDecodeError as e:
            await msg.reply(f"Invalid JSON: {e}")
            return

        if not isinstance(new_config, dict):
            await msg.reply("The JSON must be a dictionary/object.")
            return

        self.bot.config_manager.replace_config(new_config)
        await msg.reply("Config updated successfully.")
        try:
            await msg.delete()
        except discord.HTTPException:
            pass


async def setup(bot: "TicketBot"):
    await bot.add_cog(DebugCog(bot))
