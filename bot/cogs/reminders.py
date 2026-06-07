import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
import json

if TYPE_CHECKING:
    from main import TicketBot


class ReminderCog(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot
        self.check_inactive_tickets.start()

    def cog_unload(self):
        self.check_inactive_tickets.cancel()

    @tasks.loop(hours=1)
    async def check_inactive_tickets(self):
        await self.bot.wait_until_ready()
        now = datetime.now(timezone.utc)
        two_days_ago = now - timedelta(days=2)
        one_day_ago = now - timedelta(days=1)

        for guild in self.bot.guilds:
            tickets = await self.bot.db.get_assigned_open_tickets(guild.id)
            for ticket in tickets:
                last_reminder = ticket.get("last_reminder_at")
                if last_reminder:
                    try:
                        reminder_time = datetime.fromisoformat(last_reminder)
                        if reminder_time > one_day_ago:
                            continue
                    except (ValueError, TypeError):
                        pass

                channel = guild.get_channel(ticket["channel_id"])
                if not channel:
                    continue

                assigned_ids = json.loads(ticket["assigned_ids"])
                inactive_users = []

                for user_id in assigned_ids:
                    try:
                        has_messaged = False
                        async for msg in channel.history(after=two_days_ago, limit=200):
                            if msg.author.id == user_id:
                                has_messaged = True
                                break
                    except (discord.Forbidden, discord.HTTPException):
                        continue

                    if not has_messaged:
                        inactive_users.append(user_id)

                if not inactive_users:
                    continue

                reminded = False
                for user_id in inactive_users:
                    user = guild.get_member(user_id)
                    if not user:
                        continue
                    try:
                        embed = discord.Embed(
                            title="Ticket Reminder",
                            description=(
                                f"You are assigned to **Ticket #{ticket['id']}** "
                                f"(<#{ticket['channel_id']}>) which has been inactive for over 2 days.\n\n"
                                f"If you are no longer working on this ticket, please unclaim it using "
                                f"`/unclaim` in the ticket channel."
                            ),
                            color=discord.Color.orange(),
                        )
                        embed.set_footer(text=f"Ticket #{ticket['id']} | {guild.name}")
                        await user.send(embed=embed)
                        reminded = True
                    except (discord.Forbidden, discord.HTTPException):
                        pass

                if reminded:
                    await self.bot.db.update_ticket_reminder(
                        ticket["id"], now.isoformat()
                    )

    @check_inactive_tickets.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: "TicketBot"):
    await bot.add_cog(ReminderCog(bot))
