import discord
from discord import app_commands
from discord.ext import commands
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from main import TicketBot


class SetupCog(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot

    setup_group = app_commands.Group(name="setup", description="Bot configuration commands")

    @setup_group.command(name="category", description="Add or edit a ticket category")
    @app_commands.describe(
        name="Category name",
        discord_category="Discord category channel",
        role_name="Role name to create/use"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_category(self, interaction: discord.Interaction, name: str, discord_category: discord.CategoryChannel, role_name: Optional[str] = None):
        if not role_name:
            role_name = f"{name}-ticket"
        self.bot.config_manager.set_category(name, discord_category.id, role_name)
        await interaction.response.send_message(f"Category '{name}' configured with role '{role_name}'.", ephemeral=True)

    async def _category_autocomplete(self, interaction: discord.Interaction, current: str):
        categories = self.bot.config_manager.get_categories()
        return [
            app_commands.Choice(name=name, value=name)
            for name in categories if current.lower() in name.lower()
        ][:25]

    @setup_group.command(name="questions", description="Set questions for a category")
    @app_commands.describe(category="Category name", questions="Comma-separated list of questions")
    @app_commands.autocomplete(category=_category_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_questions(self, interaction: discord.Interaction, category: str, questions: str):
        q_list = [q.strip() for q in questions.split(",") if q.strip()]
        try:
            self.bot.config_manager.set_questions(category, q_list)
            await interaction.response.send_message(f"Questions set for '{category}'.", ephemeral=True)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    @setup_group.command(name="panel", description="Send the ticket creation panel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        from cogs.tickets import CreateTicketButton
        embed = discord.Embed(
            title="Support Tickets",
            description="Click the button below to create a ticket.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed, view=CreateTicketButton())
        await interaction.response.send_message(f"Panel sent to {channel.mention}.", ephemeral=True)

    @setup_group.command(name="stats", description="Set the stats channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_stats(self, interaction: discord.Interaction, channel: discord.TextChannel):
        # Main stats message
        embed1 = discord.Embed(title="Ticket Stats", description="Open Tickets: 0\nStaff Loads:\nNone", color=discord.Color.purple())
        msg1 = await channel.send(embed=embed1)
        await msg1.pin()

        # Leaderboard message
        from cogs.stats import StatsLeaderboardView
        view = StatsLeaderboardView(self.bot)
        embed2 = await view.refresh(interaction.guild)
        msg2 = await channel.send(embed=embed2, view=view)
        await msg2.pin()

        self.bot.config_manager.set_stats_channel(channel.id, msg1.id, msg2.id)
        await interaction.response.send_message(f"Stats set up in {channel.mention}.", ephemeral=True)

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await ctx.send("Pong!")

async def setup(bot: "TicketBot"):
    await bot.add_cog(SetupCog(bot))
