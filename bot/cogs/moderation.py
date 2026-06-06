import discord
from discord import app_commands
from discord.ext import commands
from typing import TYPE_CHECKING
import json
import asyncio

if TYPE_CHECKING:
    from main import TicketBot


class ModerationCog(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot

    async def _get_ticket(self, interaction: discord.Interaction) -> dict:
        ticket = await self.bot.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
        return ticket

    async def _update_embed(self, channel: discord.TextChannel, ticket: dict):
        async for msg in channel.history(limit=50):
            if msg.embeds and msg.embeds[0].title and msg.embeds[0].title.startswith("Ticket #"):
                embed = msg.embeds[0]
                assigned_ids = json.loads(ticket["assigned_ids"])
                if assigned_ids:
                    mentions = " ".join(f"<@{uid}>" for uid in assigned_ids)
                else:
                    mentions = "None"
                # Update assigned field
                for i, field in enumerate(embed.fields):
                    if field.name == "Assigned":
                        embed.set_field_at(i, name="Assigned", value=mentions, inline=False)
                        try:
                            await msg.edit(embed=embed)
                        except discord.HTTPException:
                            pass
                        return

    async def _refresh_stats(self, guild: discord.Guild):
        stats_cog = self.bot.get_cog("StatsCog")
        if stats_cog:
            await stats_cog.update_stats(guild)

    @app_commands.command(name="claim", description="Claim this ticket")
    async def claim(self, interaction: discord.Interaction):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        assigned = json.loads(ticket["assigned_ids"])
        if interaction.user.id in assigned:
            await interaction.response.send_message("You already claimed this ticket.", ephemeral=True)
            return

        assigned.append(interaction.user.id)
        await self.bot.db.update_ticket_assigned(ticket["id"], assigned)
        ticket["assigned_ids"] = json.dumps(assigned)
        await self.bot.db.add_ticket_log(ticket["id"], "claim", interaction.user.id)

        channel = interaction.channel
        await channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await self._update_embed(channel, ticket)
        await interaction.response.send_message(f"{interaction.user.mention} claimed this ticket.")
        await self._refresh_stats(interaction.guild)

    @app_commands.command(name="assign", description="Assign a staff member to this ticket")
    @app_commands.describe(user="User to assign")
    async def assign(self, interaction: discord.Interaction, user: discord.Member):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        assigned = json.loads(ticket["assigned_ids"])
        if user.id in assigned:
            await interaction.response.send_message("User is already assigned.", ephemeral=True)
            return

        assigned.append(user.id)
        await self.bot.db.update_ticket_assigned(ticket["id"], assigned)
        ticket["assigned_ids"] = json.dumps(assigned)
        await self.bot.db.add_ticket_log(ticket["id"], "assign", interaction.user.id, {"assigned_user": user.id})

        channel = interaction.channel
        await channel.set_permissions(user, view_channel=True, send_messages=True)
        await self._update_embed(channel, ticket)
        await interaction.response.send_message(f"{user.mention} has been assigned to this ticket.")
        await self._refresh_stats(interaction.guild)

    @app_commands.command(name="unclaim", description="Unclaim this ticket")
    async def unclaim(self, interaction: discord.Interaction):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        assigned = json.loads(ticket["assigned_ids"])
        if interaction.user.id not in assigned:
            await interaction.response.send_message("You have not claimed this ticket.", ephemeral=True)
            return

        assigned.remove(interaction.user.id)
        await self.bot.db.update_ticket_assigned(ticket["id"], assigned)
        ticket["assigned_ids"] = json.dumps(assigned)
        await self.bot.db.add_ticket_log(ticket["id"], "unclaim", interaction.user.id)

        channel = interaction.channel
        await channel.set_permissions(interaction.user, overwrite=None)
        await self._update_embed(channel, ticket)
        await interaction.response.send_message(f"{interaction.user.mention} unclaimed this ticket.")
        await self._refresh_stats(interaction.guild)

    @app_commands.command(name="add", description="Add a user to this ticket")
    @app_commands.describe(user="User to add")
    async def add_user(self, interaction: discord.Interaction, user: discord.Member):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        channel = interaction.channel
        await channel.set_permissions(user, view_channel=True, send_messages=True)
        await self.bot.db.add_ticket_log(ticket["id"], "add_user", interaction.user.id, {"added_user": user.id})
        await interaction.response.send_message(f"{user.mention} has been added to this ticket.")

    @app_commands.command(name="remove", description="Remove a user from this ticket")
    @app_commands.describe(user="User to remove")
    async def remove_user(self, interaction: discord.Interaction, user: discord.Member):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        channel = interaction.channel
        await channel.set_permissions(user, overwrite=None)
        await self.bot.db.add_ticket_log(ticket["id"], "remove_user", interaction.user.id, {"removed_user": user.id})
        await interaction.response.send_message(f"{user.mention} has been removed from this ticket.")

    @app_commands.command(name="close", description="Close this ticket")
    @app_commands.describe(reason="Reason for closing")
    async def close(self, interaction: discord.Interaction, reason: str = None):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is already closed.", ephemeral=True)
            return

        await interaction.response.send_message("Closing ticket and saving transcript...", ephemeral=True)

        channel = interaction.channel
        # Save transcript
        async for msg in channel.history(limit=None, oldest_first=True):
            attachments = [a.url for a in msg.attachments]
            await self.bot.db.add_transcript_message(
                ticket["id"], msg.id, msg.author.id, msg.author.display_name,
                msg.content, msg.created_at, attachments
            )

        await self.bot.db.close_ticket(ticket["id"], reason)
        await self.bot.db.add_ticket_log(ticket["id"], "close", interaction.user.id, {"reason": reason})

        await interaction.followup.send(f"Ticket closed. Reason: {reason or 'No reason provided.'}")
        await self._refresh_stats(interaction.guild)

        await interaction.followup.send("This channel will be deleted in 5 seconds...")
        await asyncio.sleep(5)
        await channel.delete(reason=f"Ticket closed by {interaction.user}")

    @app_commands.command(name="rename", description="Rename this ticket channel")
    @app_commands.describe(name="New channel name")
    async def rename(self, interaction: discord.Interaction, name: str):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        await interaction.channel.edit(name=name)
        await self.bot.db.add_ticket_log(ticket["id"], "rename", interaction.user.id, {"new_name": name})
        await interaction.response.send_message(f"Channel renamed to `{name}`.")

async def setup(bot: "TicketBot"):
    await bot.add_cog(ModerationCog(bot))
