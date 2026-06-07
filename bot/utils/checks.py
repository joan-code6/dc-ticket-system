import discord
from discord import app_commands
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import TicketBot


async def has_staff_role(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True

    bot: "TicketBot" = interaction.client
    role_id = bot.config_manager.get_staff_role()
    if role_id is None:
        raise app_commands.CheckFailure(
            "No staff role has been configured. An admin must use `/setup staffrole` first."
        )

    guild = interaction.guild
    if guild is None:
        raise app_commands.CheckFailure("This command can only be used in a server.")

    role = guild.get_role(role_id)
    if role is None:
        raise app_commands.CheckFailure(
            "The configured staff role no longer exists. An admin must reconfigure it with `/setup staffrole`."
        )

    if role not in interaction.user.roles:
        raise app_commands.CheckFailure(
            "You must have the staff role to use this command."
        )

    return True


async def check_staff_role(interaction: discord.Interaction) -> bool:
    bot: "TicketBot" = interaction.client
    role_id = bot.config_manager.get_staff_role()

    if interaction.user.guild_permissions.administrator:
        return True

    if role_id is None:
        await interaction.response.send_message(
            "No staff role configured. An admin must use `/setup staffrole` first.",
            ephemeral=True,
        )
        return False

    guild = interaction.guild
    if guild is None:
        return False

    role = guild.get_role(role_id)
    if role is None:
        await interaction.response.send_message(
            "Configured staff role no longer exists. An admin must reconfigure it.",
            ephemeral=True,
        )
        return False

    if role not in interaction.user.roles:
        await interaction.response.send_message(
            "You must have the staff role to use this.",
            ephemeral=True,
        )
        return False

    return True
