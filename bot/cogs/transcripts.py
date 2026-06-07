import discord
from discord import app_commands
from discord.ext import commands
from typing import TYPE_CHECKING, Optional
from datetime import datetime
import json

if TYPE_CHECKING:
    from main import TicketBot

from utils.checks import has_staff_role


class TranscriptView(discord.ui.View):
    def __init__(self, pages: list):
        super().__init__(timeout=180)
        self.pages = pages
        self.current = 0

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current > 0:
            self.current -= 1
            await interaction.response.edit_message(embed=self.pages[self.current])
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current < len(self.pages) - 1:
            self.current += 1
            await interaction.response.edit_message(embed=self.pages[self.current])
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
        after="ISO date after",
        before="ISO date before"
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
            filters["after"] = after
        if before:
            filters["before"] = before

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

    @transcript_group.command(name="view", description="View a transcript by ticket ID")
    @app_commands.describe(ticket_id="Ticket ID")
    @app_commands.check(has_staff_role)
    async def transcript_view(self, interaction: discord.Interaction, ticket_id: int):
        ticket = await self.bot.db.get_ticket_by_id(ticket_id)
        if not ticket or ticket["guild_id"] != interaction.guild_id:
            await interaction.response.send_message("Ticket not found.", ephemeral=True)
            return

        messages = await self.bot.db.get_transcript_messages(ticket_id)
        if not messages:
            await interaction.response.send_message("No transcript messages found.", ephemeral=True)
            return

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
                embed = discord.Embed(title=f"Transcript #{ticket_id} (Page {len(pages)+1})", description="".join(chunk), color=discord.Color.greyple())
                pages.append(embed)
                chunk = [line]
                chunk_size = len(line)
            else:
                chunk.append(line)
                chunk_size += len(line)

        if chunk:
            embed = discord.Embed(title=f"Transcript #{ticket_id} (Page {len(pages)+1})", description="".join(chunk), color=discord.Color.greyple())
            pages.append(embed)

        if len(pages) == 1:
            await interaction.response.send_message(embed=pages[0], ephemeral=True)
        else:
            await interaction.response.send_message(embed=pages[0], view=TranscriptView(pages), ephemeral=True)

async def setup(bot: "TicketBot"):
    await bot.add_cog(TranscriptsCog(bot))
