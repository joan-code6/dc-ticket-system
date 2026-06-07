import discord
from discord import app_commands
from discord.ext import commands
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from main import TicketBot

SETUP_BYPASS_ROLE = 1314666319035240579


def _has_setup_access():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        if interaction.user.get_role(SETUP_BYPASS_ROLE):
            return True
        raise app_commands.MissingPermissions(["Administrator"])
    return app_commands.check(predicate)


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
    @_has_setup_access()
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
    @_has_setup_access()
    async def setup_questions(self, interaction: discord.Interaction, category: str, questions: str):
        q_list = [q.strip() for q in questions.split(",") if q.strip()]
        try:
            self.bot.config_manager.set_questions(category, q_list)
            await interaction.response.send_message(f"Questions set for '{category}'.", ephemeral=True)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    @setup_group.command(name="panel", description="Send the ticket creation panel")
    @_has_setup_access()
    async def setup_panel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        from cogs.tickets import CreateTicketButton
        title = self.bot.config_manager.get_panel_title()
        description = self.bot.config_manager.get_panel_description()
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.purple()
        )
        await channel.send(embed=embed, view=CreateTicketButton())
        await interaction.response.send_message(f"Panel sent to {channel.mention}.", ephemeral=True)

    @setup_group.command(name="stats", description="Set the stats channel")
    @_has_setup_access()
    async def setup_stats(self, interaction: discord.Interaction, channel: discord.TextChannel):
        # Main stats message
        embed1 = discord.Embed(title="Ticket Stats", description="Open Tickets: 0\nStaff Loads:\nNone", color=discord.Color.purple())
        msg1 = await channel.send(embed=embed1)
        await msg1.pin()

        # Leaderboard message
        from cogs.stats import StatsLeaderboardView, ClaimsLeaderboardView
        lb_view = StatsLeaderboardView(self.bot)
        embed2 = await lb_view.refresh(interaction.guild)
        msg2 = await channel.send(embed=embed2, view=lb_view)
        await msg2.pin()

        # Claims leaderboard message
        claims_lb_view = ClaimsLeaderboardView(self.bot)
        embed3 = await claims_lb_view.refresh(interaction.guild)
        msg3 = await channel.send(embed=embed3, view=claims_lb_view)
        await msg3.pin()

        self.bot.config_manager.set_stats_channel(channel.id, msg1.id, msg2.id, msg3.id)
        await interaction.response.send_message(f"Stats set up in {channel.mention}.", ephemeral=True)

    @setup_group.command(name="archive", description="Set the channel for archiving ticket attachments")
    @_has_setup_access()
    async def setup_archive(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.bot.config_manager.set_archive_channel(channel.id)
        await interaction.response.send_message(
            f"Archive channel set to {channel.mention}. Ticket attachments will be saved here before channel deletion.",
            ephemeral=True,
        )

    @setup_group.command(name="staffrole", description="Set the role used for leaderboard tracking (shows staff even with 0 tickets)")
    @_has_setup_access()
    async def setup_staff_role(self, interaction: discord.Interaction, role: discord.Role):
        self.bot.config_manager.set_staff_role(role.id)
        await interaction.response.send_message(f"Staff role set to {role.mention}. Leaderboards will include all members with this role.", ephemeral=True)

    @setup_group.command(name="dashboard", description="Set the ticket dashboard channel (stats + ping role selector)")
    @_has_setup_access()
    async def setup_dashboard(self, interaction: discord.Interaction, channel: discord.TextChannel):
        from cogs.stats import CategoryPingView, StatsCog
        stats_cog = self.bot.get_cog("StatsCog")
        embed = await stats_cog._build_stats_embed(interaction.guild) if stats_cog else discord.Embed(title="Ticket Stats", description="Open Tickets: 0\nStaff Loads:\nNone", color=discord.Color.purple())
        view = CategoryPingView(self.bot)
        msg = await channel.send(embed=embed, view=view)
        self.bot.config_manager.set_dashboard(channel.id, msg.id)
        await interaction.response.send_message(f"Dashboard set up in {channel.mention}.", ephemeral=True)

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        await ctx.send("Pong!")

async def setup(bot: "TicketBot"):
    await bot.add_cog(SetupCog(bot))
