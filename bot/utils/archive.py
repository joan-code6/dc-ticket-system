import io
import asyncio
from typing import TYPE_CHECKING, Dict

import aiohttp
import discord

if TYPE_CHECKING:
    from utils.database import Database

MAX_FILE_SIZE = 25 * 1024 * 1024


async def archive_attachments(
    bot: discord.Client,
    channel: discord.TextChannel,
    ticket_id: int,
    db: "Database",
    archive_channel_id: int,
    ticket_name: str = "",
) -> int:
    archive_channel = bot.get_channel(archive_channel_id)
    if not archive_channel or not isinstance(archive_channel, discord.TextChannel):
        return 0

    replacements: Dict[str, str] = {}
    count = 0

    async with aiohttp.ClientSession() as session:
        async for msg in channel.history(limit=None, oldest_first=True):
            for att in msg.attachments:
                if att.size > MAX_FILE_SIZE:
                    continue

                try:
                    async with session.get(att.url) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.read()
                except Exception:
                    continue

                filename = att.filename or att.url.split("/")[-1].split("?")[0]
                try:
                    discord_file = discord.File(io.BytesIO(data), filename=filename)
                    context = f"**Ticket #{ticket_id}**" if ticket_id else "Ticket"
                    if ticket_name:
                        context += f" ({ticket_name})"
                    sent = await archive_channel.send(
                        content=f"{context} — `{filename}`",
                        file=discord_file,
                    )
                except Exception:
                    continue

                if sent.attachments:
                    new_url = sent.attachments[0].url
                    replacements[att.url] = new_url
                    count += 1

                await asyncio.sleep(0.5)

    if replacements:
        await db.update_transcript_attachment_urls(ticket_id, replacements)

    return count
