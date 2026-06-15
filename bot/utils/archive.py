import io
import asyncio
from typing import TYPE_CHECKING, Dict

import aiohttp
import discord

if TYPE_CHECKING:
    from utils.database import Database

DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=120)


async def archive_single_attachment(
    bot: discord.Client,
    archive_channel_id: int,
    ticket_id: int,
    ticket_name: str,
    attachment_url: str,
    filename: str = "",
) -> str | None:
    archive_channel = bot.get_channel(archive_channel_id)
    if not archive_channel or not isinstance(archive_channel, discord.TextChannel):
        return None

    if not filename:
        filename = attachment_url.split("/")[-1].split("?")[0]

    try:
        async with aiohttp.ClientSession(timeout=DOWNLOAD_TIMEOUT) as session:
            async with session.get(attachment_url) as resp:
                if resp.status != 200:
                    print(f"  [archive] HTTP {resp.status} downloading: {filename}")
                    return None
                data = await resp.read()
    except asyncio.TimeoutError:
        print(f"  [archive] Timed out downloading: {filename}")
        return None
    except Exception as e:
        print(f"  [archive] Download failed: {filename} ({e})")
        return None

    try:
        discord_file = discord.File(io.BytesIO(data), filename=filename)
        context = f"**Ticket #{ticket_id}**" if ticket_id else "Ticket"
        if ticket_name:
            context += f" ({ticket_name})"
        sent = await archive_channel.send(
            content=f"{context} — `{filename}`",
            file=discord_file,
        )
    except discord.HTTPException as e:
        if e.code == 40005:
            print(f"  [archive] File too large for upload: {filename}")
        else:
            print(f"  [archive] Upload failed: {filename} ({e})")
        return None
    except Exception as e:
        print(f"  [archive] Upload failed: {filename} ({e})")
        return None

    if sent.attachments:
        print(f"  [archive] OK: {filename}")
        return sent.attachments[0].url
    return None


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
    failed = 0

    async with aiohttp.ClientSession(timeout=DOWNLOAD_TIMEOUT) as session:
        async for msg in channel.history(limit=None, oldest_first=True):
            for att in msg.attachments:
                filename = att.filename or att.url.split("/")[-1].split("?")[0]

                try:
                    async with session.get(att.url) as resp:
                        if resp.status != 200:
                            print(f"  [archive] HTTP {resp.status} downloading: {filename}")
                            failed += 1
                            continue
                        data = await resp.read()
                except asyncio.TimeoutError:
                    print(f"  [archive] Timed out downloading: {filename}")
                    failed += 1
                    continue
                except Exception as e:
                    print(f"  [archive] Download failed: {filename} ({e})")
                    failed += 1
                    continue

                try:
                    discord_file = discord.File(io.BytesIO(data), filename=filename)
                    context = f"**Ticket #{ticket_id}**" if ticket_id else "Ticket"
                    if ticket_name:
                        context += f" ({ticket_name})"
                    sent = await archive_channel.send(
                        content=f"{context} — `{filename}`",
                        file=discord_file,
                    )
                except discord.HTTPException as e:
                    if e.code == 40005:
                        print(f"  [archive] File too large for upload: {filename} ({att.size} bytes)")
                    else:
                        print(f"  [archive] Upload failed: {filename} ({e})")
                    failed += 1
                    continue
                except Exception as e:
                    print(f"  [archive] Upload failed: {filename} ({e})")
                    failed += 1
                    continue

                if sent.attachments:
                    new_url = sent.attachments[0].url
                    replacements[att.url] = new_url
                    count += 1
                    print(f"  [archive] OK: {filename} ({att.size} bytes)")

                await asyncio.sleep(0.5)

    if replacements:
        await db.update_transcript_attachment_urls(ticket_id, replacements)

    if failed:
        print(f"  [archive] Summary: {count} archived, {failed} failed")
    return count
