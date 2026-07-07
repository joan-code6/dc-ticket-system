import discord
from discord import app_commands
from discord.ext import commands
from typing import TYPE_CHECKING
import json

if TYPE_CHECKING:
    from main import TicketBot

from utils.checks import has_staff_role
from utils import ai


async def _move_category_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    from main import TicketBot
    bot: TicketBot = interaction.client
    categories = bot.config_manager.get_category_names()
    matches = [c for c in categories if current.lower() in c.lower()]
    return [app_commands.Choice(name=c[:100], value=c[:100]) for c in matches[:25]]


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
                for i, field in enumerate(embed.fields):
                    if field.name == "Assigned":
                        embed.set_field_at(i, name="Assigned", value=mentions, inline=False)
                        try:
                            await msg.edit(embed=embed)
                        except discord.HTTPException:
                            pass
                        return

    async def _update_embed_category(self, channel: discord.TextChannel, new_category: str):
        async for msg in channel.history(limit=50):
            if msg.embeds and msg.embeds[0].title and msg.embeds[0].title.startswith("Ticket #"):
                embed = msg.embeds[0]
                for i, field in enumerate(embed.fields):
                    if field.name == "Category":
                        embed.set_field_at(i, name="Category", value=new_category, inline=True)
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
    @app_commands.check(has_staff_role)
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
    @app_commands.check(has_staff_role)
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

    @app_commands.command(name="unassign", description="Unassign a staff member from this ticket")
    @app_commands.describe(user="User to unassign")
    @app_commands.check(has_staff_role)
    async def unassign(self, interaction: discord.Interaction, user: discord.Member):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        assigned = json.loads(ticket["assigned_ids"])
        if user.id not in assigned:
            await interaction.response.send_message(f"{user.mention} is not assigned to this ticket.", ephemeral=True)
            return

        assigned.remove(user.id)
        await self.bot.db.update_ticket_assigned(ticket["id"], assigned)
        ticket["assigned_ids"] = json.dumps(assigned)
        await self.bot.db.add_ticket_log(ticket["id"], "unassign", interaction.user.id, {"unassigned_user": user.id})

        channel = interaction.channel
        await channel.set_permissions(user, overwrite=None)
        await self._update_embed(channel, ticket)
        await interaction.response.send_message(f"{user.mention} has been unassigned from this ticket.")
        await self._refresh_stats(interaction.guild)

    @app_commands.command(name="unclaim", description="Unclaim this ticket")
    @app_commands.check(has_staff_role)
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
    @app_commands.check(has_staff_role)
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
    @app_commands.check(has_staff_role)
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
    @app_commands.check(has_staff_role)
    async def close(self, interaction: discord.Interaction, reason: str = None):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is already closed.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        async for msg in channel.history(limit=None, oldest_first=True):
            attachments = [a.url for a in msg.attachments]
            await self.bot.db.add_transcript_message(
                ticket["id"], msg.id, msg.author.id, msg.author.display_name,
                msg.content, msg.created_at, attachments
            )

        await self.bot.db.close_ticket(ticket["id"], reason)
        await self.bot.db.add_ticket_log(ticket["id"], "close", interaction.user.id, {"reason": reason})

        creator = interaction.guild.get_member(ticket["creator_id"])
        if creator:
            await channel.set_permissions(creator, view_channel=True, send_messages=False)

        await self._refresh_stats(interaction.guild)

        reason_text = f"\nReason: {reason}" if reason else ""
        await interaction.followup.send("Ticket closed.", ephemeral=True)

        from cogs.tickets import CloseActionView
        await channel.send(
            f"🔒 This ticket has been closed by {interaction.user.mention}.{reason_text}",
            view=CloseActionView()
        )

    @app_commands.command(name="reopen", description="Reopen a closed ticket")
    @app_commands.check(has_staff_role)
    async def reopen(self, interaction: discord.Interaction):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] != "closed":
            await interaction.response.send_message("This ticket is not closed.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        await self.bot.db.reopen_ticket(ticket["id"])
        await self.bot.db.add_ticket_log(ticket["id"], "reopen", interaction.user.id)

        channel = interaction.channel
        creator = interaction.guild.get_member(ticket["creator_id"])
        if creator:
            await channel.set_permissions(creator, view_channel=True, send_messages=True)

        await self._refresh_stats(interaction.guild)

        await interaction.followup.send("Ticket reopened.", ephemeral=True)
        await channel.send(f"🔓 Ticket reopened by {interaction.user.mention}.")

    @app_commands.command(name="rename", description="Rename this ticket channel")
    @app_commands.describe(name="New channel name")
    @app_commands.check(has_staff_role)
    async def rename(self, interaction: discord.Interaction, name: str):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        await interaction.channel.edit(name=name)
        await self.bot.db.set_ticket_title(ticket["id"], name)
        await self.bot.db.add_ticket_log(ticket["id"], "rename", interaction.user.id, {"new_name": name})
        await interaction.response.send_message(f"Channel renamed to `{name}`.")

    @app_commands.command(name="move", description="Move this ticket to another category")
    @app_commands.describe(category="Target category")
    @app_commands.autocomplete(category=_move_category_autocomplete)
    @app_commands.check(has_staff_role)
    async def move(self, interaction: discord.Interaction, category: str):
        ticket = await self._get_ticket(interaction)
        if not ticket:
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        old_category = ticket["category"]
        if old_category == category:
            await interaction.response.send_message(
                "This ticket is already in that category.", ephemeral=True
            )
            return

        cfg = self.bot.config_manager.get_category(category)
        if not cfg:
            names = self.bot.config_manager.get_category_names()
            hint = f" Available: {', '.join(f'`{n}`' for n in names[:10])}"
            if len(names) > 10:
                hint += f" (+{len(names) - 10} more)"
            await interaction.response.send_message(
                f"Category `{category}` not found.{hint}", ephemeral=True
            )
            return

        guild = interaction.guild
        discord_category = guild.get_channel(cfg["discord_category_id"])
        if not discord_category:
            await interaction.response.send_message(
                "Target category channel not found on this server.", ephemeral=True
            )
            return

        channel = interaction.channel

        old_cfg = self.bot.config_manager.get_category(old_category)
        new_role = None
        new_role_name = cfg["role_name"]
        new_role = discord.utils.get(guild.roles, name=new_role_name)
        if not new_role:
            new_role = await guild.create_role(
                name=new_role_name, reason="Ticket system auto-created role"
            )

        if old_cfg:
            old_role_name = old_cfg["role_name"]
            if old_role_name != new_role_name:
                old_role = discord.utils.get(guild.roles, name=old_role_name)
                if old_role:
                    await channel.set_permissions(old_role, overwrite=None)

        await channel.set_permissions(new_role, view_channel=True, send_messages=True)

        await self.bot.db.update_ticket_category(ticket["id"], category)
        await self.bot.db.add_ticket_log(
            ticket["id"], "move", interaction.user.id,
            {"old_category": old_category, "new_category": category}
        )

        await channel.edit(category=discord_category)
        await self._update_embed_category(channel, category)
        await self._refresh_stats(guild)
        await interaction.response.send_message(
            f"Ticket moved from **{old_category}** to **{category}**."
        )

    @app_commands.command(name="ai-summarize", description="Summarize this ticket using AI")
    @app_commands.check(has_staff_role)
    async def ai_summarize(self, interaction: discord.Interaction):
        if not ai.is_available():
            await interaction.response.send_message(
                "AI features are not configured. Set the `HC_AI_API_KEY` environment variable.",
                ephemeral=True,
            )
            return

        ticket = await self._get_ticket(interaction)
        if not ticket:
            return

        if ai.is_processing(ticket["id"]):
            await interaction.response.send_message(
                "An AI operation is already running for this ticket. Please wait.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        ai.mark_processing(ticket["id"])
        try:
            msgs = await self.bot.db.get_transcript_messages(ticket["id"])
            if not msgs:
                await interaction.followup.send("No transcript messages found for this ticket.", ephemeral=True)
                return

            conversation_lines = []
            for m in msgs:
                content = m["content"] or ""
                if not content.strip():
                    continue
                conversation_lines.append(f"{m['author_name']}: {content}")
            if not conversation_lines:
                await interaction.followup.send("No text content found in transcript.", ephemeral=True)
                return
            conversation = "\n".join(conversation_lines)

            summary = await ai.summarize_ticket(conversation)
            if summary is None:
                await interaction.followup.send("AI summarization failed. The API may be unavailable.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"Ticket #{ticket['id']} — AI Summary",
                description=summary,
                color=discord.Color.blue(),
            )
            await interaction.followup.send(embed=embed)
        except Exception:
            await interaction.followup.send("An error occurred during summarization.", ephemeral=True)
        finally:
            ai.unmark_processing(ticket["id"])

    @app_commands.command(name="ai-rename", description="Rename this ticket channel using AI")
    @app_commands.check(has_staff_role)
    async def ai_rename(self, interaction: discord.Interaction):
        if not ai.is_available():
            await interaction.response.send_message(
                "AI features are not configured. Set the `HC_AI_API_KEY` environment variable.",
                ephemeral=True,
            )
            return

        ticket = await self._get_ticket(interaction)
        if not ticket:
            return

        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        if ai.is_processing(ticket["id"]):
            await interaction.response.send_message(
                "An AI operation is already running for this ticket. Please wait.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        ai.mark_processing(ticket["id"])
        try:
            msgs = await self.bot.db.get_recent_transcript_messages(ticket["id"], limit=30)
            if len(msgs) < 2:
                await interaction.followup.send("Not enough messages to suggest a name.", ephemeral=True)
                return

            conversation_lines = []
            for m in msgs:
                content = m["content"] or ""
                if not content.strip():
                    continue
                conversation_lines.append(f"{m['author_name']}: {content}")
            if not conversation_lines:
                await interaction.followup.send("No text content found in transcript.", ephemeral=True)
                return
            conversation = "\n".join(conversation_lines)

            title = await ai.suggest_ticket_title(conversation)
            if title is None:
                await interaction.followup.send("Could not determine a suitable name from the conversation.", ephemeral=True)
                return

            old_name = interaction.channel.name
            await interaction.channel.edit(name=title)
            await self.bot.db.set_ticket_title(ticket["id"], title)
            await self.bot.db.add_ticket_log(
                ticket["id"],
                "rename",
                interaction.user.id,
                {"old_name": old_name, "new_name": title, "ai": True},
            )
            await interaction.followup.send(f"Channel renamed to `{title}`.")
        except Exception:
            await interaction.followup.send("An error occurred during rename.", ephemeral=True)
        finally:
            ai.unmark_processing(ticket["id"])

async def setup(bot: "TicketBot"):
    await bot.add_cog(ModerationCog(bot))
