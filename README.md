# Discord Ticket Bot — User Guide

A full-featured ticket system built with `discord.py`. Create tickets via a button panel, assign staff, track interactions, save transcripts, and more.

---

## Table of Contents

- [Admin Setup](#admin-setup)
  - [Prerequisites](#prerequisites)
  - [1. Create a ticket category](#1-create-a-ticket-category)
  - [2. Add questions (optional)](#2-add-questions-optional)
  - [3. Send the ticket panel](#3-send-the-ticket-panel)
  - [4. Set up the stats channel](#4-set-up-the-stats-channel)
  - [5. Set the archive channel](#5-set-the-archive-channel)
  - [6. Set the transcript log channel](#6-set-the-transcript-log-channel)
  - [7. Set up the dashboard](#7-set-up-the-dashboard)
  - [8. Set the staff role (optional)](#8-set-the-staff-role-optional)
  - [Managing categories](#managing-categories)
- [Moderator Usage](#moderator-usage)
  - [Quick actions (buttons)](#quick-actions-buttons)
  - [Claiming a ticket](#claiming-a-ticket)
  - [Assigning another staff member](#assigning-another-staff-member)
  - [Unclaiming](#unclaiming)
  - [Unassigning a staff member](#unassigning-a-staff-member)
  - [Adding external users](#adding-external-users)
  - [Removing users](#removing-users)
  - [Renaming the ticket](#renaming-the-ticket)
  - [Closing a ticket](#closing-a-ticket)
- [Inactivity Reminders](#inactivity-reminders)
- [Transcripts](#transcripts)
  - [Searching transcripts](#searching-transcripts)
  - [Viewing transcripts](#viewing-transcripts)
- [Stats Channel](#stats-channel)
  - [Main panel](#main-panel)
  - [Interaction leaderboard](#interaction-leaderboard)
  - [Claims leaderboard](#claims-leaderboard)
- [Dashboard](#dashboard)

---

## Admin Setup

> All admin commands require the **Administrator** permission.

### Prerequisites

1. Create a **Discord category channel** where ticket channels will be created (e.g. `🎫 Tickets`).
2. The bot requires the following permissions in that category:
   - Manage Channels
   - Manage Permissions
   - View Channel
   - Send Messages
   - Manage Messages
   - Read Message History

### 1. Create a ticket category

```
/setup category name:<category-name> discord_category:<the-category-channel> [role_name:<custom-role>]
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `name` | Yes | Internal name for this ticket type (e.g. `Support`, `Bug Report`) |
| `discord_category` | Yes | The Discord category channel where tickets are created |
| `role_name` | Optional | Name of the role to create/use for staff who should see tickets. Defaults to `<name>-ticket` (e.g. `Support-ticket`) |

**What happens:** The bot creates a role with the given name and uses it to grant access to ticket channels. Staff members who should see all tickets in this category should be given this role.

> Tip: Include a Discord custom emoji in the category name (e.g. `<:bug:...> Bug Report`) — it will appear in the ticket creation dropdown.

**Example:**
```
/setup category name:Support discord_category:#tickets role_name:support-ticket
```

### 2. Add questions (optional)

You can define up to 5 questions that users answer before their ticket is created. Answers appear in the ticket's opening embed.

Question format: `<text>[:style]` where `style` is `short` (single-line, default) or `long` (multi-line paragraph).

```
/setup questions category:<category-name> questions:<comma-separated list>
```

**Example:**
```
/setup questions category:Support questions:What is your in-game name?,Describe your issue:long,What server are you on?
```

The `category` parameter has autocomplete — it shows your configured categories as you type.

### 3. Send the ticket panel

Posts the main "Create Ticket" button to a channel. Users click this to open a ticket.

```
/setup panel channel:<#channel>
```

**What happens:** An embed with a "Create Ticket" button is sent to the chosen channel. When a user clicks it, they pick a category, answer questions (if any exist), and a private ticket channel is created. Each user can only have **one open ticket at a time** — attempting to create another shows an error directing them to their existing ticket.

### 4. Set up the stats channel

Creates three pinned messages in a dedicated stats channel:
- A live **open tickets & staff loads** panel
- An **interaction leaderboard** with buttons to cycle between Today / Week / Month / All-Time
- A **claims leaderboard** tracking how many tickets each staff member has claimed

```
/setup stats channel:<#channel>
```

> Pro tip: Create a dedicated `#ticket-stats` channel that only staff can see. Run this command once per server.

### 5. Set the archive channel

When a ticket is closed, all attachments (images, files, etc.) are downloaded and re-uploaded to this channel for permanent storage. This prevents broken attachment links in transcripts after the ticket channel is deleted.

```
/setup archive channel:<#channel>
```

> The archive channel should be a staff-only channel. Transcript links are automatically updated to point to the archived copies.

### 6. Set the transcript log channel

When a ticket is deleted (via the **Delete** button), a summary embed is posted here. The summary includes the ticket ID, category, creator, assigned staff, timestamps, and close reason — plus a note to use `/transcript view <id>` for the full transcript.

```
/setup transcript channel:<#channel>
```

> Unlike the archive channel (which stores raw attachment files), this channel is a readable log of closed tickets for staff reference.

### 7. Set up the dashboard

Creates a public dashboard with live ticket stats and a **category ping role selector**. Users can self-assign ping roles for specific ticket categories so they get notified when tickets are opened in categories they care about.

```
/setup dashboard channel:<#channel>
```

The dashboard embed shows:
- Open ticket count
- Per-category breakdown
- A multi-select dropdown for users to choose which ping roles they want

> Run this in a public channel where users can see it.

### 8. Set the staff role (optional)

Assign an existing Discord role to be tracked on the leaderboards. Members with this role always appear on the interaction and claims leaderboards, even if they have 0 tickets for the selected period.

```
/setup staffrole role:<@role>
```

### Managing categories

- **Add more categories:** Run `/setup category` again with a different name.
- **Edit a category:** Run `/setup category` with the same name — it overwrites the previous config.
- **Update questions:** Run `/setup questions` again to replace the question list.
- **Remove a category:** Edit `config.json` directly or implement the future `/setup category delete` command.

---

## Moderator Usage

> All commands below are **slash commands** typed directly in the ticket channel.

### Quick actions (buttons)

Every ticket channel includes two buttons at the top for instant access:

| Button | Effect |
|--------|--------|
| **Assign to Me** | Self-assigns you to the ticket (same as `/claim`) |
| **Close Ticket** | Closes the ticket, locks the channel, and shows Delete / Reopen buttons |

No slash command needed — just click.

### Claiming a ticket

```
/claim
```

Adds you to the ticket's assigned staff list. You gain channel permissions, your name appears in the ticket embed, and the stats channel updates.

### Assigning another staff member

```
/assign user:<@user>
```

Assigns another staff member to the ticket. Supports Discord's built-in user autocomplete.

### Unclaiming

```
/unclaim
```

Removes you from the assigned staff list and revokes your extra channel permissions.

### Unassigning a staff member

```
/unassign user:<@user>
```

Removes a specific staff member from the assigned staff list and revokes their channel permissions. Useful when a staff member no longer needs to be on the ticket or was assigned by mistake.

### Adding external users

```
/add user:<@user>
```

Grants any user **View Channel** and **Send Messages** permissions for this ticket without assigning them as staff. Useful for bringing in a witness, translator, or additional reporter.

### Removing users

```
/remove user:<@user>
```

Revokes the extra permissions granted by `/add`.

### Renaming the ticket

```
/rename name:<new-name>
```

Renames the ticket channel. The opening embed is not affected — only the channel name changes.

### Closing a ticket

```
/close [reason]
```

Or click the **Close Ticket** button in the ticket channel.

1. Saves the **entire channel transcript** (every message, including attachments) to the database.
2. **Locks the channel** — the ticket creator can no longer send messages, but staff can still type.
3. Posts the close reason.
4. Displays **Delete** and **Reopen** buttons below the close message.

| Button | Effect |
|--------|--------|
| **Delete** | Posts a ticket summary to the transcript log channel, archives all attachments, then permanently deletes the channel. |
| **Reopen** | Reopens the ticket, restoring the creator's ability to send messages. |

> The transcript is searchable and viewable later via `/transcript`. Attachments are only archived to permanent storage when **Delete** is clicked. The transcript log channel (if configured) receives a summary embed so staff can review closed tickets at a glance.

---

## Inactivity Reminders

The bot automatically monitors assigned tickets for staff inactivity. If no staff member has posted in a ticket for **2 days**, the bot sends a private DM to all assigned staff members as a nudge.

- Checks run **every hour**.
- Each ticket only gets one reminder — the bot won't spam you.
- Resets if a staff member posts in the ticket again.

> Only applies to tickets that have been *claimed* or *assigned*.

---

## Transcripts

Closed ticket transcripts are saved automatically. Use the following commands to retrieve them.

### Searching transcripts

```
/transcript search [user:<@user>] [category:<name>] [after:<date>] [before:<date>]
```

All parameters are optional — combine them to narrow results. Returns up to 25 matching tickets.

**Examples:**
```
/transcript search user:@Joan
/transcript search category:Support after:2026-05-01
```

### Viewing transcripts

```
/transcript view ticket_id:<id>
```

Shows a paginated transcript of the ticket. Use the **Prev** / **Next** buttons to scroll through messages. Each message shows:
- Author display name
- Timestamp
- Content
- Attachments (if any)

---

## Stats Channel

### Main panel

Updates in real-time whenever tickets are opened, claimed, assigned, or closed.

```
Open Tickets: 7
Staff Loads:
@admin1 — 3
@admin2 — 1

Unclaimed Tickets (2):
• #user3 (Support) by @user3
• #user4 (Bug Report) by @user4
```

### Interaction leaderboard

The second pinned message shows a leaderboard of staff interactions. Use the **◀ ▶** buttons to cycle through:

| View | Range |
|------|-------|
| Today | Interactions since midnight UTC |
| This Week | Last 7 days |
| This Month | Last 30 days |
| All Time | Since the bot was set up |

If a **staff role** is configured via `/setup staffrole`, all members with that role appear on the leaderboard — even those with 0 interactions.

Each staff member's count is the **number of distinct tickets** they've interacted with (claimed, assigned, closed, etc.), including closed tickets.

### Claims leaderboard

The third pinned message tracks only **claim actions** (when a staff member takes ownership of a ticket). Same Today / Week / Month / All-Time cycling with the same **◀ ▶** buttons.

---

## Dashboard

The dashboard (set up via `/setup dashboard`) provides a public-facing view of ticket activity:

- **Live open ticket count** and per-category breakdown.
- **Category ping role selector** — a multi-select dropdown where users can self-assign or remove ping roles for specific ticket categories.

When a new ticket is created in a category, anyone with that category's ping role is mentioned in the ticket channel. Users control their own notifications through the dashboard dropdown — no admin intervention needed.

---

## Running the Bot

### Prerequisites

1. Create a `.env` file in the project root with your bot token:
   ```
   DC_TOKEN=your-bot-token-here
   ```
2. Ensure your bot has the following Discord intents enabled in the Developer Portal:
   - Server Members Intent
   - Message Content Intent

### Linux/macOS

Uses a **user systemd service** (no root needed, runs under your user):

```bash
./run.sh            # Install, enable & start the service
./run.sh start      # Start
./run.sh stop       # Stop
./run.sh restart    # Restart
./run.sh status     # Service status + recent logs
./run.sh logs       # Tail live logs (Ctrl+C to stop)
./run.sh uninstall  # Stop, disable & remove service
```

The script auto-creates a `venv/` and installs dependencies on first run.
Logs are written to `bot.log` in the project directory.

### Windows

```powershell
.\run.ps1           # Foreground session with auto-reload (Ctrl+C to stop)
```
