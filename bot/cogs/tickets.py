import discord
from discord import ui
from discord.ext import commands
from typing import TYPE_CHECKING
import json
import asyncio
import re

if TYPE_CHECKING:
    from main import TicketBot

from utils.archive import archive_attachments
from utils.checks import check_staff_role


class TicketCategorySelect(ui.Select):
    def __init__(self, categories: dict):
        options = []
        for name in categories.keys():
            cfg = categories[name]
            match = re.match(r'^<(a?:)?(\w+):(\d+)>\s*(.*)', name)
            if match:
                emoji_name = match.group(2)
                emoji_id = int(match.group(3))
                label = match.group(4)
                emoji = discord.PartialEmoji(name=emoji_name, id=emoji_id)
            else:
                label = name
                emoji = None
            description = cfg.get("description", f"Create a {label} ticket")
            options.append(
                discord.SelectOption(label=label, value=name, emoji=emoji, description=description)
            )
        super().__init__(placeholder="Choose a ticket category...", min_values=1, max_values=1, options=options, custom_id="ticket_category_select")
        self.categories = categories

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        cfg = self.categories[category]
        questions = cfg.get("questions", [])

        # Check if user already has an open ticket
        bot: TicketBot = interaction.client
        existing = await bot.db.get_open_ticket_by_user(interaction.user.id, interaction.guild_id)
        if existing:
            await interaction.response.send_message("You already have an open ticket!", ephemeral=True)
            return

        if not questions:
            await interaction.response.defer(ephemeral=True)
            await self.create_ticket(interaction, category, {})
            return

        modal = TicketQuestionsModal(category, questions, self.create_ticket)
        await interaction.response.send_modal(modal)

    async def create_ticket(self, interaction: discord.Interaction, category: str, answers: dict):
        bot: TicketBot = interaction.client
        cfg = bot.config_manager.get_category(category)
        if not cfg:
            await interaction.followup.send("Category configuration missing.", ephemeral=True)
            return

        guild = interaction.guild
        creator = interaction.user
        discord_category = guild.get_channel(cfg["discord_category_id"])
        if not discord_category:
            await interaction.followup.send("Ticket category channel not found.", ephemeral=True)
            return

        # Role setup
        role_name = cfg["role_name"]
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role = await guild.create_role(name=role_name, reason="Ticket system auto-created role")

        # Channel naming
        base_name = creator.name.lower()
        existing_channels = [c.name for c in guild.channels if c.name.startswith(base_name)]
        if base_name in existing_channels:
            count = 1
            while f"{base_name}-{count}" in existing_channels:
                count += 1
            channel_name = f"{base_name}-{count}"
        else:
            channel_name = base_name

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            creator: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        channel = await guild.create_text_channel(
            name=channel_name,
            category=discord_category,
            overwrites=overwrites,
            reason=f"Ticket created by {creator}"
        )

        ticket_id = await bot.db.create_ticket(guild.id, channel.id, creator.id, category)
        await bot.db.add_ticket_log(ticket_id, "open", creator.id, {"answers": answers})

        embed = discord.Embed(title=f"Ticket #{ticket_id}", color=discord.Color.blue())
        embed.add_field(name="Creator", value=creator.mention, inline=True)
        embed.add_field(name="Category", value=category, inline=True)
        embed.add_field(name="Assigned", value="None", inline=False)
        if answers:
            for q, a in answers.items():
                embed.add_field(name=q, value=a or "No answer", inline=False)

        await channel.send(content=f"{role.mention} {creator.mention}", embed=embed, view=TicketActionView())
        await interaction.followup.send(f"Ticket created: {channel.mention}", ephemeral=True)

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
        label_match = re.match(r'^<(a?:)?\w+:\d+>\s*(.*)', category)
        name = label_match.group(2) if label_match else category
        super().__init__(title=f"{name} Ticket")
        self.category = category
        self.on_submit_callback = on_submit_callback
        self.question_map = {}
        for i, question in enumerate(questions[:5]):
            text_input = ui.TextInput(label=question[:45], style=discord.TextStyle.short, required=False, custom_id=f"q{i}")
            self.question_map[f"q{i}"] = question[:45]
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        answers = {}
        for child in self.children:
            if isinstance(child, ui.TextInput):
                answers[self.question_map[child.custom_id]] = child.value
        await interaction.response.defer(ephemeral=True)
        await self.on_submit_callback(interaction, self.category, answers)


class TicketActionView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close_button")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        bot: TicketBot = interaction.client
        if not await check_staff_role(interaction):
            return
        ticket = await bot.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is already closed.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        channel = interaction.channel
        async for msg in channel.history(limit=None, oldest_first=True):
            attachments = [a.url for a in msg.attachments]
            await bot.db.add_transcript_message(
                ticket["id"], msg.id, msg.author.id, msg.author.display_name,
                msg.content, msg.created_at, attachments
            )

        await bot.db.close_ticket(ticket["id"])
        await bot.db.add_ticket_log(ticket["id"], "close", interaction.user.id)

        stats_cog = bot.get_cog("StatsCog")
        if stats_cog:
            await stats_cog.update_stats(interaction.guild)

        archive_channel_id = bot.config_manager.get_archive_channel()
        if archive_channel_id:
            await archive_attachments(
                bot, channel, ticket["id"], bot.db, archive_channel_id,
                ticket_name=f"#{ticket['id']}",
            )

        await interaction.followup.send("Ticket closed and transcript saved.", ephemeral=True)
        await channel.send("This channel will be deleted in 5 seconds...")
        await asyncio.sleep(5)
        await channel.delete(reason=f"Ticket closed by {interaction.user}")

    @ui.button(label="Assign to Me", style=discord.ButtonStyle.green, custom_id="ticket_assign_button")
    async def assign_to_me(self, interaction: discord.Interaction, button: ui.Button):
        bot: TicketBot = interaction.client
        if not await check_staff_role(interaction):
            return
        ticket = await bot.db.get_ticket_by_channel(interaction.channel_id)
        if not ticket:
            await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
            return
        if ticket["status"] == "closed":
            await interaction.response.send_message("This ticket is closed.", ephemeral=True)
            return

        assigned = json.loads(ticket["assigned_ids"])
        if interaction.user.id in assigned:
            await interaction.response.send_message("You are already assigned to this ticket.", ephemeral=True)
            return

        await interaction.response.defer()

        assigned.append(interaction.user.id)
        await bot.db.update_ticket_assigned(ticket["id"], assigned)
        ticket["assigned_ids"] = json.dumps(assigned)
        await bot.db.add_ticket_log(ticket["id"], "claim", interaction.user.id)

        channel = interaction.channel
        await channel.set_permissions(interaction.user, view_channel=True, send_messages=True)

        async for msg in channel.history(limit=50):
            if msg.embeds and msg.embeds[0].title and msg.embeds[0].title.startswith("Ticket #"):
                embed = msg.embeds[0]
                mentions = " ".join(f"<@{uid}>" for uid in assigned)
                for i, field in enumerate(embed.fields):
                    if field.name == "Assigned":
                        embed.set_field_at(i, name="Assigned", value=mentions, inline=False)
                        try:
                            await msg.edit(embed=embed)
                        except discord.HTTPException:
                            pass
                        break
                break

        stats_cog = bot.get_cog("StatsCog")
        if stats_cog:
            await stats_cog.update_stats(interaction.guild)

        await interaction.followup.send(f"{interaction.user.mention} has been assigned to this ticket.")


class CreateTicketButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Create Ticket", style=discord.ButtonStyle.secondary, emoji="🎫", custom_id="create_ticket_button")
    async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
        bot: TicketBot = interaction.client
        categories = bot.config_manager.get_categories()
        if not categories:
            await interaction.response.send_message("No ticket categories configured.", ephemeral=True)
            return
        view = TicketCategoryView(categories)
        await interaction.response.send_message("Select a category:", view=view, ephemeral=True)


class TicketsCog(commands.Cog):
    def __init__(self, bot: "TicketBot"):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(CreateTicketButton())
        self.bot.add_view(TicketActionView())
        categories = self.bot.config_manager.get_categories()
        if categories:
            self.bot.add_view(TicketCategoryView(categories))

async def setup(bot: "TicketBot"):
    await bot.add_cog(TicketsCog(bot))
