import discord
from discord import ui
from discord.ext import commands
from typing import TYPE_CHECKING
import json

if TYPE_CHECKING:
    from main import TicketBot


class TicketCategorySelect(ui.Select):
    def __init__(self, categories: dict):
        options = [
            discord.SelectOption(label=name, value=name, description=f"Create a {name} ticket")
            for name in categories.keys()
        ]
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
            await self.create_ticket(interaction, category, {})
            return

        modal = TicketQuestionsModal(category, questions, self.create_ticket)
        await interaction.response.send_modal(modal)

    async def create_ticket(self, interaction: discord.Interaction, category: str, answers: dict):
        bot: TicketBot = interaction.client
        cfg = bot.config_manager.get_category(category)
        if not cfg:
            await interaction.response.send_message("Category configuration missing.", ephemeral=True)
            return

        guild = interaction.guild
        creator = interaction.user
        discord_category = guild.get_channel(cfg["discord_category_id"])
        if not discord_category:
            await interaction.response.send_message("Ticket category channel not found.", ephemeral=True)
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

        await channel.send(content=f"{role.mention} {creator.mention}", embed=embed)
        await interaction.response.send_message(f"Ticket created: {channel.mention}", ephemeral=True)

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
        super().__init__(title=f"{category.title()} Ticket")
        self.category = category
        self.on_submit_callback = on_submit_callback
        self.answers = {}
        for i, question in enumerate(questions[:5]):
            text_input = ui.TextInput(label=question[:45], style=discord.TextStyle.short, required=False)
            setattr(self, f"q{i}", text_input)
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        answers = {}
        for child in self.children:
            if isinstance(child, ui.TextInput):
                answers[str(child.label)] = child.value
        await self.on_submit_callback(interaction, self.category, answers)


class CreateTicketButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="create_ticket_button")
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
        categories = self.bot.config_manager.get_categories()
        if categories:
            self.bot.add_view(TicketCategoryView(categories))

async def setup(bot: "TicketBot"):
    await bot.add_cog(TicketsCog(bot))
