import discord
from discord import ui
from discord.ext import commands
from typing import TYPE_CHECKING
from datetime import datetime, timezone
import asyncio
import json
import re

if TYPE_CHECKING:
    from main import TicketBot

from utils.archive import archive_single_attachment
from utils.checks import check_staff_role
from utils import ai
from cogs.transcripts import TranscriptSummaryView


def _format_discord_time(ts_str: str | None) -> str | None:
    if not ts_str:
        return None
    try:
        if "T" in ts_str:
            dt = datetime.fromisoformat(ts_str)
        else:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
        return f"<t:{int(dt.timestamp())}:R>"
    except Exception:
        return ts_str


async def build_ticket_summary(
    bot: "TicketBot", ticket: dict, guild: discord.Guild
) -> discord.Embed:
    embed = discord.Embed(
        title=f"Ticket #{ticket['id']} — Deleted", color=discord.Color.dark_red()
    )
    embed.add_field(name="Category", value=ticket["category"], inline=True)

    creator = guild.get_member(ticket["creator_id"])
    embed.add_field(
        name="Creator",
        value=creator.mention if creator else f"<@{ticket['creator_id']}>",
        inline=True,
    )

    assigned_ids = json.loads(ticket["assigned_ids"])
    assigned_text = "None"
    if assigned_ids:
        mentions = []
        for uid in assigned_ids:
            member = guild.get_member(uid)
            mentions.append(member.mention if member else f"<@{uid}>")
        assigned_text = ", ".join(mentions)
    embed.add_field(name="Assigned Staff", value=assigned_text, inline=False)

    created_str = _format_discord_time(ticket["created_at"])
    closed_str = _format_discord_time(ticket["closed_at"])
    embed.add_field(name="Created", value=created_str or "Unknown", inline=True)
    embed.add_field(name="Closed", value=closed_str or "Unknown", inline=True)

    closer_id = await bot.db.get_ticket_closer(ticket["id"])
    if closer_id:
        closer = guild.get_member(closer_id)
        embed.add_field(
            name="Closed by",
            value=closer.mention if closer else f"<@{closer_id}>",
            inline=True,
        )

    close_reason = ticket.get("close_reason")
    if close_reason:
        embed.add_field(name="Close Reason", value=close_reason, inline=False)

    user_counts = await bot.db.get_user_message_counts(ticket["id"])
    if user_counts:
        lines = []
        for uc in user_counts:
            author_id = uc["author_id"]
            author_name = uc["author_name"]
            count = uc["count"]
            lines.append(f"`{count}` - <@{author_id}> - {author_name}")
        embed.add_field(
            name="Users in Transcript", value="\n".join(lines), inline=False
        )

    embed.add_field(
        name="Full Transcript",
        value=f"Use `/transcript view {ticket['id']}` to see all messages.",
        inline=False,
    )

    return embed


class TicketCategorySelect(ui.Select):
    def __init__(self, categories: dict):
        options = []
        for name in categories.keys():
            cfg = categories[name]
            match = re.match(r"^<(a?:)?(\w+):(\d+)>\s*(.*)", name)
            if match:
                emoji_name = match.group(2)
                emoji_id = int(match.group(3))
                label = match.group(4)
                emoji = discord.PartialEmoji(name=emoji_name, id=emoji_id)
            else:
                label = name
                emoji = None
            options.append(discord.SelectOption(label=label, value=name, emoji=emoji))
        super().__init__(
            placeholder="Choose a ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_category_select",
        )
        self.categories = categories

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        cfg = self.categories[category]
        questions = cfg.get("questions", [])

        # Check if user already has an open ticket
        bot: TicketBot = interaction.client
        existing = await bot.db.get_open_ticket_by_user(
            interaction.user.id, interaction.guild_id
        )
        if existing:
            await interaction.response.send_message(
                "You already have an open ticket! Please close it before opening a new one.",
                ephemeral=True,
            )
            return

        if not questions:
            await interaction.response.defer(ephemeral=True)
            await self.create_ticket(interaction, category, {}, questions)
            return

        modal = TicketQuestionsModal(category, questions, self.create_ticket)
        await interaction.response.send_modal(modal)

    async def create_ticket(
        self, interaction: discord.Interaction, category: str, answers: dict,
        questions: list | None = None
    ):
        bot: TicketBot = interaction.client
        cfg = bot.config_manager.get_category(category)
        if not cfg:
            await interaction.followup.send(
                "Category configuration missing.", ephemeral=True
            )
            return

        guild = interaction.guild
        creator = interaction.user
        discord_category = guild.get_channel(cfg["discord_category_id"])
        if not discord_category:
            await interaction.followup.send(
                "Ticket category channel not found.", ephemeral=True
            )
            return

        # Role setup
        role_name = cfg["role_name"]
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role = await guild.create_role(
                name=role_name, reason="Ticket system auto-created role"
            )

        # Channel naming
        base_name = creator.name.lower()
        existing_channels = [
            c.name for c in guild.channels if c.name.startswith(base_name)
        ]
        if base_name in existing_channels:
            count = 1
            while f"{base_name}-{count}" in existing_channels:
                count += 1
            channel_name = f"{base_name}-{count}"
        else:
            channel_name = base_name

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_channels=True
            ),
            creator: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        channel = await guild.create_text_channel(
            name=channel_name,
            category=discord_category,
            overwrites=overwrites,
            reason=f"Ticket created by {creator}",
        )

        ticket_id = await bot.db.create_ticket(
            guild.id, channel.id, creator.id, category
        )
        await bot.db.add_ticket_log(ticket_id, "open", creator.id, {"answers": answers})

        embed = discord.Embed(title=f"Ticket #{ticket_id}", color=discord.Color.blue())
        embed.add_field(name="Creator", value=creator.mention, inline=True)
        embed.add_field(name="Category", value=category, inline=True)
        embed.add_field(name="Assigned", value="None", inline=False)
        if answers:
            for q, a in answers.items():
                embed.add_field(name=q[:256], value=a or "No answer", inline=False)

        msg = await channel.send(
            content=f"{role.mention} {creator.mention}",
            embed=embed,
            view=TicketActionView(),
        )

        opening_lines = [f"**Ticket #{ticket_id} opened**", f"Category: {category}"]
        if questions:
            opening_lines.append("")
            opening_lines.append("**Starting Questions:**")
            for i, q in enumerate(questions):
                q_text = q.get("text", "") if isinstance(q, dict) else q
                answer = answers.get(q_text)
                if answer:
                    opening_lines.append(f"**{q_text}**: {answer}")
                else:
                    opening_lines.append(f"**{q_text}**: [Not asked]")
        elif answers:
            opening_lines.append("")
            for q, a in answers.items():
                opening_lines.append(f"**{q}**: {a or 'No answer'}")
        opening_content = "\n".join(opening_lines)
        await bot.db.add_transcript_message(
            ticket_id,
            msg.id,
            bot.user.id,
            bot.user.display_name,
            opening_content,
            msg.created_at,
            [],
        )

        await interaction.followup.send(
            f"Ticket created: {channel.mention}", ephemeral=True
        )

        # Update stats
        stats_cog = bot.get_cog("StatsCog")
        if stats_cog:
            await stats_cog.update_stats(guild)


class TicketCategoryView(ui.View):
    def __init__(self, categories: dict):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect(categories))


class TicketQuestionsModal(ui.Modal):
    def __init__(self, category: str, questions: list, on_submit_callback):
        label_match = re.match(r"^<(a?:)?\w+:\d+>\s*(.*)", category)
        name = label_match.group(2) if label_match else category
        super().__init__(title=f"{name} Ticket")
        self.category = category
        self.questions = questions
        self.on_submit_callback = on_submit_callback
        self.question_map = {}
        for i, q in enumerate(questions[:5]):
            if isinstance(q, dict):
                text = q.get("text", "")
                required = q.get("required", False)
                style = (
                    discord.TextStyle.long
                    if q.get("style") == "long"
                    else discord.TextStyle.short
                )
            else:
                text = q
                required = False
                style = discord.TextStyle.short
            label = text[:45]
            text_input = ui.TextInput(
                label=label, style=style, required=required, custom_id=f"q{i}"
            )
            self.question_map[f"q{i}"] = text
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        answers = {}
        for child in self.children:
            if isinstance(child, ui.TextInput):
                answers[self.question_map[child.custom_id]] = child.value
        await interaction.response.defer(ephemeral=True)
        await self.on_submit_callback(interaction, self.category, answers, self.questions)


class TicketActionView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_button",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        bot: TicketBot = interaction.client
        ticket = await bot.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "This is not a ticket channel.", ephemeral=True
            )
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message(
                "This ticket is already closed.", ephemeral=True
            )
            return

        if interaction.user.id == ticket["creator_id"]:
            await interaction.response.send_message(
                "Close request sent. A staff member will review it.", ephemeral=True
            )
            await bot.db.add_ticket_log(
                ticket["id"], "close_request", interaction.user.id
            )
            embed = discord.Embed(
                title="Close Request",
                description=f"{interaction.user.mention} has requested this ticket be closed.",
                color=discord.Color.orange(),
            )
            await interaction.channel.send(embed=embed, view=CloseRequestView())
            return

        if not await check_staff_role(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        async for msg in channel.history(limit=None, oldest_first=True):
            attachments = [a.url for a in msg.attachments]
            await bot.db.add_transcript_message(
                ticket["id"],
                msg.id,
                msg.author.id,
                msg.author.display_name,
                msg.content,
                msg.created_at,
                attachments,
            )

        await bot.db.close_ticket(ticket["id"])
        await bot.db.add_ticket_log(ticket["id"], "close", interaction.user.id)

        creator = interaction.guild.get_member(ticket["creator_id"])
        if creator:
            await channel.set_permissions(
                creator, view_channel=True, send_messages=False
            )

        stats_cog = bot.get_cog("StatsCog")
        if stats_cog:
            await stats_cog.update_stats(interaction.guild)

        await interaction.followup.send("Ticket closed.", ephemeral=True)
        await channel.send(
            f"🔒 This ticket has been closed by {interaction.user.mention}.",
            view=CloseActionView(),
        )

    @ui.button(
        label="Assign to Me",
        style=discord.ButtonStyle.green,
        custom_id="ticket_assign_button",
    )
    async def assign_to_me(self, interaction: discord.Interaction, button: ui.Button):
        bot: TicketBot = interaction.client
        if not await check_staff_role(interaction):
            return
        ticket = await bot.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "This is not a ticket channel.", ephemeral=True
            )
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message(
                "This ticket is closed.", ephemeral=True
            )
            return

        assigned = json.loads(ticket["assigned_ids"])
        if interaction.user.id in assigned:
            await interaction.response.send_message(
                "You are already assigned to this ticket.", ephemeral=True
            )
            return

        await interaction.response.defer()

        assigned.append(interaction.user.id)
        await bot.db.update_ticket_assigned(ticket["id"], assigned)
        ticket["assigned_ids"] = json.dumps(assigned)
        await bot.db.add_ticket_log(ticket["id"], "claim", interaction.user.id)

        channel = interaction.channel
        await channel.set_permissions(
            interaction.user, view_channel=True, send_messages=True
        )

        async for msg in channel.history(limit=50):
            if (
                msg.embeds
                and msg.embeds[0].title
                and msg.embeds[0].title.startswith("Ticket #")
            ):
                embed = msg.embeds[0]
                mentions = " ".join(f"<@{uid}>" for uid in assigned)
                for i, field in enumerate(embed.fields):
                    if field.name == "Assigned":
                        embed.set_field_at(
                            i, name="Assigned", value=mentions, inline=False
                        )
                        try:
                            await msg.edit(embed=embed)
                        except discord.HTTPException:
                            pass
                        break
                break

        stats_cog = bot.get_cog("StatsCog")
        if stats_cog:
            await stats_cog.update_stats(interaction.guild)

        await interaction.followup.send(
            f"{interaction.user.mention} has been assigned to this ticket."
        )


class CloseActionView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Delete",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_delete_button",
    )
    async def delete_ticket(self, interaction: discord.Interaction, button: ui.Button):
        bot: TicketBot = interaction.client
        if not await check_staff_role(interaction):
            return
        ticket = await bot.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "This is not a ticket channel.", ephemeral=True
            )
            return
        if ticket["status"] != "closed":
            await interaction.response.send_message(
                "This ticket is not closed.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel

        transcript_channel_id = bot.config_manager.get_transcript_channel()
        if transcript_channel_id:
            transcript_channel = interaction.guild.get_channel(transcript_channel_id)
            if transcript_channel:
                embed = await build_ticket_summary(bot, ticket, interaction.guild)
                await transcript_channel.send(embed=embed, view=TranscriptSummaryView())

        await channel.delete(reason=f"Ticket deleted by {interaction.user}")

    @ui.button(
        label="Reopen",
        style=discord.ButtonStyle.green,
        custom_id="ticket_reopen_button",
    )
    async def reopen_ticket(self, interaction: discord.Interaction, button: ui.Button):
        bot: TicketBot = interaction.client
        if not await check_staff_role(interaction):
            return
        ticket = await bot.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "This is not a ticket channel.", ephemeral=True
            )
            return
        if ticket["status"] != "closed":
            await interaction.response.send_message(
                "This ticket is not closed.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        await bot.db.reopen_ticket(ticket["id"])
        await bot.db.add_ticket_log(ticket["id"], "reopen", interaction.user.id)

        channel = interaction.channel
        creator = interaction.guild.get_member(ticket["creator_id"])
        if creator:
            await channel.set_permissions(
                creator, view_channel=True, send_messages=True
            )

        stats_cog = bot.get_cog("StatsCog")
        if stats_cog:
            await stats_cog.update_stats(interaction.guild)

        await interaction.message.edit(
            view=None, content=interaction.message.content + "\n\n✅ Reopened"
        )
        await channel.send(f"🔓 Ticket reopened by {interaction.user.mention}.")
        await interaction.followup.send("Ticket reopened.", ephemeral=True)


class CloseRequestView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Approve & Close",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close_request_button",
    )
    async def approve_close(self, interaction: discord.Interaction, button: ui.Button):
        bot: TicketBot = interaction.client
        if not await check_staff_role(interaction):
            return
        ticket = await bot.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message(
                "This is not a ticket channel.", ephemeral=True
            )
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message(
                "This ticket is already closed.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel

        async for msg in channel.history(limit=None, oldest_first=True):
            attachments = [a.url for a in msg.attachments]
            await bot.db.add_transcript_message(
                ticket["id"],
                msg.id,
                msg.author.id,
                msg.author.display_name,
                msg.content,
                msg.created_at,
                attachments,
            )

        await bot.db.close_ticket(ticket["id"])
        await bot.db.add_ticket_log(
            ticket["id"], "close", interaction.user.id, {"via": "close_request"}
        )

        creator = interaction.guild.get_member(ticket["creator_id"])
        if creator:
            await channel.set_permissions(
                creator, view_channel=True, send_messages=False
            )

        transcript_channel_id = bot.config_manager.get_transcript_channel()
        if transcript_channel_id:
            transcript_channel = interaction.guild.get_channel(transcript_channel_id)
            if transcript_channel:
                try:
                    embed = await build_ticket_summary(bot, ticket, interaction.guild)
                    await transcript_channel.send(embed=embed, view=TranscriptSummaryView())
                except Exception:
                    pass

        stats_cog = bot.get_cog("StatsCog")
        if stats_cog:
            await stats_cog.update_stats(interaction.guild)

        await interaction.message.edit(view=None)

        await channel.delete(
            reason=f"Ticket closed by {interaction.user} via close request"
        )


class CreateTicketButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.secondary,
        emoji="🎫",
        custom_id="create_ticket_button",
    )
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        bot: TicketBot = interaction.client
        categories = bot.config_manager.get_categories()
        if not categories:
            await interaction.response.send_message(
                "No ticket categories configured.", ephemeral=True
            )
            return
        view = TicketCategoryView(categories)
        await interaction.response.send_message(
            "Select a category:", view=view, ephemeral=True
        )


class TicketsCog(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        if message.author.bot:
            return
        ticket = await self.bot.db.get_ticket_by_channel(message.channel.id)
        if not ticket:
            return
        archive_channel_id = self.bot.config_manager.get_archive_channel()
        attachments = []
        for att in message.attachments:
            if archive_channel_id:
                archived_url = await archive_single_attachment(
                    self.bot,
                    archive_channel_id,
                    ticket["id"],
                    f"#{ticket['id']}",
                    att.url,
                    att.filename,
                )
                attachments.append(archived_url if archived_url else att.url)
            else:
                attachments.append(att.url)

        await self.bot.db.add_transcript_message(
            ticket["id"],
            message.id,
            message.author.id,
            message.author.display_name,
            message.content,
            message.created_at,
            attachments,
        )

        if ticket["status"] != "open":
            return
        if ticket.get("title") is not None:
            return
        if not ai.is_available():
            return
        if ai.is_processing(ticket["id"]):
            return

        ai.mark_processing(ticket["id"])
        try:
            msgs = await self.bot.db.get_recent_transcript_messages(
                ticket["id"], limit=30
            )
            if len(msgs) < 2:
                return
            conversation_lines = []
            for m in msgs:
                content = m["content"] or ""
                if not content.strip():
                    continue
                conversation_lines.append(f"{m['author_name']}: {content}")
            if not conversation_lines:
                return
            conversation = "\n".join(conversation_lines)

            title = await ai.suggest_ticket_title(conversation)
            if title is None:
                return

            await self.bot.db.set_ticket_title(ticket["id"], title)
            await self.bot.db.add_ticket_log(
                ticket["id"],
                "rename",
                self.bot.user.id,
                {"old_name": message.channel.name, "new_name": title, "ai": True},
            )
            await message.channel.edit(name=title)
        except Exception:
            pass
        finally:
            ai.unmark_processing(ticket["id"])

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not after.guild:
            return
        if after.author.bot:
            return
        ticket = await self.bot.db.get_ticket_by_channel(after.channel.id)
        if not ticket:
            return
        archive_channel_id = self.bot.config_manager.get_archive_channel()
        attachments = []
        for att in after.attachments:
            if archive_channel_id:
                archived_url = await archive_single_attachment(
                    self.bot,
                    archive_channel_id,
                    ticket["id"],
                    f"#{ticket['id']}",
                    att.url,
                    att.filename,
                )
                attachments.append(archived_url if archived_url else att.url)
            else:
                attachments.append(att.url)

        await self.bot.db.update_transcript_message_content(
            ticket["id"], after.id, after.content, attachments
        )

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(CreateTicketButton())
        self.bot.add_view(TicketActionView())
        self.bot.add_view(CloseActionView())
        self.bot.add_view(CloseRequestView())
        self.bot.add_view(TranscriptSummaryView())
        categories = self.bot.config_manager.get_categories()
        if categories:
            self.bot.add_view(TicketCategoryView(categories))


async def setup(bot: "TicketBot"):
    await bot.add_cog(TicketsCog(bot))
