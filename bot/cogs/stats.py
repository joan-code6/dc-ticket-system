import discord
from discord.ext import commands
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
import re

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

        staff_role_id = self.bot.config_manager.get_staff_role()
        if staff_role_id:
            staff_role = guild.get_role(staff_role_id)
            if staff_role:
                for member in staff_role.members:
                    if member.id not in data:
                        data[member.id] = 0

        # Build description lines
        if not data:
            lines = ["No interactions yet."]
        else:
            lines = []
            sorted_data = sorted(data.items(), key=lambda x: -x[1])
            for i, (uid, count) in enumerate(sorted_data):
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


class ClaimsLeaderboardView(discord.ui.View):
    def __init__(self, bot: "TicketBot"):
        super().__init__(timeout=None)
        self.bot = bot
        self.current_view = 0

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="claims_leaderboard_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_view > 0:
            self.current_view -= 1
        else:
            self.current_view = len(VIEW_PERIODS) - 1
        embed = await self._build_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="claims_leaderboard_next")
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

        data = await self.bot.db.get_claims_leaderboard(guild.id, since)

        staff_role_id = self.bot.config_manager.get_staff_role()
        if staff_role_id:
            staff_role = guild.get_role(staff_role_id)
            if staff_role:
                for member in staff_role.members:
                    if member.id not in data:
                        data[member.id] = 0

        if not data:
            lines = ["No claims yet."]
        else:
            lines = []
            sorted_data = sorted(data.items(), key=lambda x: -x[1])
            for i, (uid, count) in enumerate(sorted_data):
                member = guild.get_member(uid)
                name = member.display_name if member else f"Unknown ({uid})"
                label = "ticket" if count == 1 else "tickets"
                if i == 0:
                    lines.append(f"🏆 **{name}** — {count} {label}")
                else:
                    lines.append(f"{i+1}. **{name}** — {count} {label}")

        embed = discord.Embed(
            title=f"Staff Claims Leaderboard — {period_name}",
            description="\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Use ◀ ▶ to cycle periods  •  View {self.current_view + 1}/{len(VIEW_PERIODS)}")
        return embed

    async def refresh(self, guild: discord.Guild):
        embed = await self._build_embed(guild)
        return embed


class CategoryPingSelect(discord.ui.Select):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot
        categories = bot.config_manager.get_categories()
        options = []
        for name in categories.keys():
            match = re.match(r'^<(a?:)?(\w+):(\d+)>\s*(.*)', name)
            if match:
                emoji_name = match.group(2)
                emoji_id = int(match.group(3))
                label = match.group(4)
                emoji = discord.PartialEmoji(name=emoji_name, id=emoji_id)
            else:
                label = name
                emoji = None
            options.append(discord.SelectOption(label=label, value=name, emoji=emoji))
        if not options:
            options.append(discord.SelectOption(label="No categories configured", value="__none__"))
        super().__init__(placeholder="Select categories to get pinged for...", min_values=0, max_values=len(options), options=options, custom_id="category_ping_select")

    async def callback(self, interaction: discord.Interaction):
        if "__none__" in (self.values or []):
            await interaction.response.send_message("No ping categories are configured.", ephemeral=True)
            return

        member = interaction.user
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("This can only be used in a server.", ephemeral=True)
            return

        guild = interaction.guild
        categories = self.bot.config_manager.get_categories()
        selected = set(self.values)
        to_add = []
        to_remove = []

        for name, cfg in categories.items():
            role = discord.utils.get(guild.roles, name=cfg["role_name"])
            if not role:
                continue
            has_role = role in member.roles
            wants_role = name in selected
            if wants_role and not has_role:
                to_add.append(role)
            elif not wants_role and has_role:
                to_remove.append(role)

        try:
            if to_remove:
                await member.remove_roles(*to_remove, reason="Updated ping preferences")
            if to_add:
                await member.add_roles(*to_add, reason="Updated ping preferences")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to manage these roles.", ephemeral=True)
            return

        added_str = ", ".join(r.mention for r in to_add) if to_add else ""
        removed_str = ", ".join(r.mention for r in to_remove) if to_remove else ""
        msg = "Ping preferences updated."
        if added_str:
            msg += f"\nAdded: {added_str}"
        if removed_str:
            msg += f"\nRemoved: {removed_str}"
        if not to_add and not to_remove:
            msg = "No changes made to your ping preferences."

        await interaction.response.send_message(msg, ephemeral=True)


class CategoryPingView(discord.ui.View):
    def __init__(self, bot: "TicketBot"):
        super().__init__(timeout=None)
        self.add_item(CategoryPingSelect(bot))


class StatsCog(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(StatsLeaderboardView(self.bot))
        self.bot.add_view(ClaimsLeaderboardView(self.bot))
        self.bot.add_view(CategoryPingView(self.bot))

    async def _build_stats_embed(self, guild: discord.Guild) -> discord.Embed:
        open_count = await self.bot.db.get_open_tickets_count(guild.id)
        staff_loads = await self.bot.db.get_staff_loads(guild.id)
        unclaimed = await self.bot.db.get_unclaimed_tickets(guild.id)

        lines = [f"Open Tickets: {open_count}", "Staff Loads:"]
        if staff_loads:
            for uid, count in sorted(staff_loads.items(), key=lambda x: -x[1]):
                member = guild.get_member(uid)
                name = member.mention if member else f"<@{uid}>"
                lines.append(f"{name} — {count}")
        else:
            lines.append("None")

        if unclaimed:
            lines.append("")
            lines.append(f"**Unclaimed Tickets ({len(unclaimed)}):**")
            for ticket in unclaimed[:10]:
                channel = guild.get_channel(ticket["channel_id"])
                creator = guild.get_member(ticket["creator_id"])
                chan_str = channel.mention if channel else f"#{ticket['channel_id']}"
                creator_str = creator.mention if creator else f"<@{ticket['creator_id']}>"
                lines.append(f"• {chan_str} ({ticket['category']}) by {creator_str}")
            if len(unclaimed) > 10:
                lines.append(f"*...and {len(unclaimed) - 10} more*")

        return discord.Embed(title="Ticket Stats", description="\n".join(lines), color=discord.Color.purple())

    async def update_stats(self, guild: discord.Guild):
        channel_id = self.bot.config_manager.get_stats_channel()
        message_id = self.bot.config_manager.get_stats_message()
        lb_message_id = self.bot.config_manager.get_stats_leaderboard_message()
        claims_lb_message_id = self.bot.config_manager.get_stats_claims_leaderboard_message()

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
                embed = await self._build_stats_embed(guild)
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

        # Update claims leaderboard message
        if claims_lb_message_id:
            try:
                claims_lb_msg = await channel.fetch_message(claims_lb_message_id)
            except discord.NotFound:
                pass
            else:
                view = ClaimsLeaderboardView(self.bot)
                embed = await view.refresh(guild)
                await claims_lb_msg.edit(embed=embed, view=view)

        # Update dashboard message
        dashboard_channel_id = self.bot.config_manager.get_dashboard_channel()
        dashboard_message_id = self.bot.config_manager.get_dashboard_message()
        if dashboard_channel_id and dashboard_message_id:
            dash_channel = guild.get_channel(dashboard_channel_id)
            if dash_channel:
                try:
                    dash_msg = await dash_channel.fetch_message(dashboard_message_id)
                except discord.NotFound:
                    pass
                else:
                    embed = await self._build_stats_embed(guild)
                    await dash_msg.edit(embed=embed, view=CategoryPingView(self.bot))

        # Update ticket utilization message
        util_channel_id = self.bot.config_manager.get_ticket_utilization_channel()
        util_message_id = self.bot.config_manager.get_ticket_utilization_message()
        if util_channel_id and util_message_id:
            util_channel = guild.get_channel(util_channel_id)
            if util_channel:
                try:
                    util_msg = await util_channel.fetch_message(util_message_id)
                except discord.NotFound:
                    pass
                else:
                    open_count = await self.bot.db.get_open_tickets_count(guild.id)
                    max_tickets = self.bot.config_manager.get_ticket_utilization_max_tickets()
                    embed = self._build_utilization_embed(open_count, max_tickets)
                    await util_msg.edit(embed=embed)

    @staticmethod
    def _build_utilization_embed(open_count: int, max_tickets: int) -> discord.Embed:
        pct = min(open_count / max_tickets * 100, 100) if max_tickets > 0 else 0
        filled = round(pct / 5)
        empty = 20 - filled
        bar = "█" * filled + "░" * empty

        if pct < 50:
            indicator = "🟢"
            embed_color = discord.Color.green()
            status = "✅ Our support team is available and ready to help you!"
        elif pct < 75:
            indicator = "🟡"
            embed_color = discord.Color.gold()
            status = "⏳ We're a bit busy, but we'll get to you soon!"
        elif pct < 90:
            indicator = "🟠"
            embed_color = discord.Color.orange()
            status = "⚠️ High ticket volume. Response times may be longer than usual."
        else:
            indicator = "🔴"
            embed_color = discord.Color.red()
            status = "🔴 We are currently experiencing high ticket rates. It might take time till our Moderators will be there to support you."

        now = discord.utils.utcnow()
        today = now.date()
        yesterday = today - timedelta(days=1)

        if now.date() == today:
            date_str = "Today"
        elif now.date() == yesterday:
            date_str = "Yesterday"
        else:
            date_str = now.strftime("%B %d, %Y")

        embed = discord.Embed(
            title="📊 Ticket Support Utilization",
            color=embed_color
        )
        embed.add_field(
            name=f"{indicator} Utilization",
            value=f"```\n[{bar}] {pct:.1f}%\n```\n**{open_count}** / {max_tickets} Tickets",
            inline=False
        )
        embed.add_field(
            name="📝 Status",
            value=status,
            inline=False
        )
        embed.set_footer(text=f"Updates automatically · Last Update {date_str} at {now.strftime('%H:%M:%S')}")
        return embed

    async def get_leaderboard_embed(self, guild: discord.Guild) -> discord.Embed:
        view = StatsLeaderboardView(self.bot)
        return await view.refresh(guild)

    async def get_claims_leaderboard_embed(self, guild: discord.Guild) -> discord.Embed:
        view = ClaimsLeaderboardView(self.bot)
        return await view.refresh(guild)


async def setup(bot: "TicketBot"):
    await bot.add_cog(StatsCog(bot))
