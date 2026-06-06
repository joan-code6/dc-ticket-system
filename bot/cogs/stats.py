import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import TicketBot

VIEW_PERIODS = [
    ("Today", "today"),
    ("This Week", "week"),
    ("This Month", "month"),
    ("All Time", "total"),
]


class StatsLeaderboardView(discord.ui.View):
    def __init__(self, bot: "TicketBot"):
        super().__init__(timeout=None)
        self.bot = bot
        self.current_view = 0

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="stats_leaderboard_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_view > 0:
            self.current_view -= 1
        else:
            self.current_view = len(VIEW_PERIODS) - 1
        embed = await self._build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="stats_leaderboard_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_view < len(VIEW_PERIODS) - 1:
            self.current_view += 1
        else:
            self.current_view = 0
        embed = await self._build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _build_embed(self, guild: discord.Guild) -> discord.Embed:
        period_name, period_key = VIEW_PERIODS[self.current_view]
        now = datetime.now(timezone.utc)

        if period_key == "today":
            since = now.strftime("%Y-%m-%d")
        elif period_key == "week":
            since = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        elif period_key == "month":
            since = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        else:
            since = None

        data = await self.bot.db.get_interaction_leaderboard(guild.id, since)

        # Build description lines
        if not data:
            lines = ["No interactions yet."]
        else:
            lines = []
            sorted_data = sorted(data.items(), key=lambda x: -x[1])
            for i, (uid, count) in enumerate(sorted_data[:15]):
                member = guild.get_member(uid)
                name = member.display_name if member else f"Unknown ({uid})"
                label = "ticket" if count == 1 else "tickets"
                if i == 0:
                    lines.append(f"🏆 **{name}** — {count} {label}")
                else:
                    lines.append(f"{i+1}. **{name}** — {count} {label}")

        embed = discord.Embed(
            title=f"Staff Interaction Leaderboard — {period_name}",
            description="\n".join(lines),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Use ◀ ▶ to cycle periods  •  View {self.current_view + 1}/{len(VIEW_PERIODS)}")
        return embed

    async def refresh(self, guild: discord.Guild):
        embed = await self._build_embed(guild)
        return embed


class StatsCog(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(StatsLeaderboardView(self.bot))

    async def update_stats(self, guild: discord.Guild):
        channel_id = self.bot.config_manager.get_stats_channel()
        message_id = self.bot.config_manager.get_stats_message()
        lb_message_id = self.bot.config_manager.get_stats_leaderboard_message()

        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return

        # Update main stats message
        if message_id:
            try:
                msg = await channel.fetch_message(message_id)
            except discord.NotFound:
                pass
            else:
                open_count = await self.bot.db.get_open_tickets_count(guild.id)
                staff_loads = await self.bot.db.get_staff_loads(guild.id)
                lines = [f"Open Tickets: {open_count}", "Staff Loads:"]
                if staff_loads:
                    for uid, count in sorted(staff_loads.items(), key=lambda x: -x[1]):
                        member = guild.get_member(uid)
                        name = member.mention if member else f"<@{uid}>"
                        lines.append(f"{name} — {count}")
                else:
                    lines.append("None")
                embed = discord.Embed(title="Ticket Stats", description="\n".join(lines), color=discord.Color.purple())
                await msg.edit(embed=embed)

        # Update leaderboard message
        if lb_message_id:
            try:
                lb_msg = await channel.fetch_message(lb_message_id)
            except discord.NotFound:
                pass
            else:
                view = StatsLeaderboardView(self.bot)
                embed = await view.refresh(guild)
                await lb_msg.edit(embed=embed, view=view)

    async def get_leaderboard_embed(self, guild: discord.Guild) -> discord.Embed:
        view = StatsLeaderboardView(self.bot)
        return await view.refresh(guild)


async def setup(bot: "TicketBot"):
    await bot.add_cog(StatsCog(bot))
