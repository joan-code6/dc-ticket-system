import discord
from discord import app_commands
from discord.ext import commands
from typing import TYPE_CHECKING, Optional
from datetime import datetime
import json
import re

if TYPE_CHECKING:
    from main import TicketBot

from utils.checks import has_staff_role
from utils.date_parser import parse_date_input, get_date_choices


async def render_transcript_pages(bot: "TicketBot", ticket_id: int) -> list[discord.Embed] | None:
    messages = await bot.db.get_transcript_messages(ticket_id)
    if not messages:
        return None

    pages = []
    chunk = []
    chunk_size = 0
    for msg in messages:
        ts = msg['timestamp']
        msg_dt = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.utcfromtimestamp(ts)
        content = msg['content'] or '[empty]'
        line = f"**[{msg['author_name']}]** <t:{int(msg_dt.timestamp())}:t>: {content}"
        if msg['attachments_json']:
            attachments = json.loads(msg['attachments_json'])
            if attachments:
                line += f"\nAttachments: {', '.join(attachments)}"
        line += "\n"

        if chunk_size + len(line) > 3900:
            embed = discord.Embed(title=f"Transcript #{ticket_id}", description="".join(chunk), color=discord.Color.greyple())
            pages.append(embed)
            chunk = [line]
            chunk_size = len(line)
        else:
            chunk.append(line)
            chunk_size += len(line)

    if chunk:
        embed = discord.Embed(title=f"Transcript #{ticket_id}", description="".join(chunk), color=discord.Color.greyple())
        pages.append(embed)

    return pages


class TranscriptSummaryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="View Transcript",
        style=discord.ButtonStyle.secondary,
        emoji="📄",
        custom_id="transcript_summary_view_button",
    )
    async def view_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        message = interaction.message
        if not message.embeds:
            await interaction.response.send_message("Cannot find ticket info.", ephemeral=True)
            return

        embed_title = message.embeds[0].title or ""
        match = re.match(r"Ticket #(\d+)", embed_title)
        if not match:
            await interaction.response.send_message("Cannot find ticket info.", ephemeral=True)
            return

        ticket_id = int(match.group(1))

        bot: TicketBot = interaction.client
        ticket = await bot.db.get_ticket_by_id(ticket_id)
        if not ticket:
            await interaction.response.send_message("Ticket not found.", ephemeral=True)
            return

        pages = await render_transcript_pages(bot, ticket_id)
        if pages is None:
            await interaction.response.send_message("No transcript messages found.", ephemeral=True)
            return

        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0], ephemeral=True)
        else:
            await interaction.response.send_message(embed=pages[0], view=TranscriptView(pages, ticket_id), ephemeral=True)


class TranscriptView(discord.ui.View):
    def __init__(self, pages: list, ticket_id: int):
        super().__init__(timeout=180)
        self.pages = pages
        self.ticket_id = ticket_id
        self.current = 0
        self._update_embed_title()

    def _update_embed_title(self):
        embed = self.pages[self.current]
        embed.title = f"Transcript #{self.ticket_id} (Page {self.current + 1}/{len(self.pages)})"

    async def _show_page(self, interaction: discord.Interaction):
        self._update_embed_title()
        await interaction.response.edit_message(embed=self.pages[self.current])

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current > 0:
            self.current -= 1
            await self._show_page(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current < len(self.pages) - 1:
            self.current += 1
            await self._show_page(interaction)
        else:
            await interaction.response.defer()


class TranscriptsCog(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot

    transcript_group = app_commands.Group(name="transcript", description="Transcript commands")

    @transcript_group.command(name="search", description="Search closed tickets")
    @app_commands.describe(
        user="Filter by user",
        category="Filter by category",
        after="Show tickets after — e.g. 7d, yesterday, June 8 2026",
        before="Show tickets before — e.g. 7d, yesterday, June 8 2026"
    )
    @app_commands.check(has_staff_role)
    async def transcript_search(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        category: Optional[str] = None,
        after: Optional[str] = None,
        before: Optional[str] = None
    ):
        filters = {}
        if user:
            filters["creator_id"] = user.id
        if category:
            filters["category"] = category
        if after:
            parsed = parse_date_input(after, end_of_day=False)
            if parsed is None:
                await interaction.response.send_message(
                    f"Invalid date: `{after}`. Try `7d`, `yesterday`, `today`, `2026-06-01`, or `June 8 2026`.",
                    ephemeral=True,
                )
                return
            filters["after"] = parsed
        if before:
            parsed = parse_date_input(before, end_of_day=True)
            if parsed is None:
                await interaction.response.send_message(
                    f"Invalid date: `{before}`. Try `7d`, `yesterday`, `today`, `2026-06-01`, or `June 8 2026`.",
                    ephemeral=True,
                )
                return
            filters["before"] = parsed

        results = await self.bot.db.search_tickets(interaction.guild_id, **filters)
        if not results:
            await interaction.response.send_message("No tickets found.", ephemeral=True)
            return

        lines = []
        for t in results[:25]:
            guild = interaction.guild
            creator = guild.get_member(t["creator_id"]) if guild else None
            creator_mention = creator.mention if creator else f"<@{t['creator_id']}>"
            created_dt = datetime.fromisoformat(t["created_at"]) if isinstance(t["created_at"], str) else datetime.utcfromtimestamp(t["created_at"])
            lines.append(f"**#{t['id']}** | {t['category']} | {creator_mention} | <t:{int(created_dt.timestamp())}:d>")

        embed = discord.Embed(title="Ticket Search Results", description="\n".join(lines), color=discord.Color.blue())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @transcript_search.autocomplete("after")
    @transcript_search.autocomplete("before")
    async def _date_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return get_date_choices(current)

    @transcript_group.command(name="view", description="View a transcript by ticket ID")
    @app_commands.describe(ticket_id="Ticket ID")
    @app_commands.check(has_staff_role)
    async def transcript_view(self, interaction: discord.Interaction, ticket_id: int):
        ticket = await self.bot.db.get_ticket_by_id(ticket_id)
        if not ticket or ticket["guild_id"] != interaction.guild_id:
            await interaction.response.send_message("Ticket not found.", ephemeral=True)
            return

        pages = await render_transcript_pages(self.bot, ticket_id)
        if pages is None:
            await interaction.response.send_message("No transcript messages found.", ephemeral=True)
            return

        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0], ephemeral=True)
        else:
            await interaction.response.send_message(embed=pages[0], view=TranscriptView(pages, ticket_id), ephemeral=True)

async def setup(bot: "TicketBot"):
    await bot.add_cog(TranscriptsCog(bot))
