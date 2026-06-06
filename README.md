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
  - [Managing categories](#managing-categories)
- [Moderator Usage](#moderator-usage)
  - [Claiming a ticket](#claiming-a-ticket)
  - [Assigning another staff member](#assigning-another-staff-member)
  - [Unclaiming](#unclaiming)
  - [Adding external users](#adding-external-users)
  - [Removing users](#removing-users)
  - [Renaming the ticket](#renaming-the-ticket)
  - [Closing a ticket](#closing-a-ticket)
  - [Next steps](#next-steps)
- [Transcripts](#transcripts)
  - [Searching transcripts](#searching-transcripts)
  - [Viewing transcripts](#viewing-transcripts)
- [Stats Channel](#stats-channel)
  - [Main panel](#main-panel)
  - [Leaderboard](#leaderboard)

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

**Example:**
```
/setup category name:Support discord_category:#tickets role_name:support-ticket
```

### 2. Add questions (optional)

You can define up to 5 questions that users answer before their ticket is created. Answers appear in the ticket's opening embed.

```
/setup questions category:<category-name> questions:<comma-separated list>
```

**Example:**
```
/setup questions category:Support questions:What is your in-game name?,What server are you on?
```

The `category` parameter has autocomplete — it shows your configured categories as you type.

### 3. Send the ticket panel

Posts the main "Create Ticket" button to a channel. Users click this to open a ticket.

```
/setup panel channel:<#channel>
```

**What happens:** An embed with a "Create Ticket" button is sent to the chosen channel. When a user clicks it, they pick a category, answer questions (if any exist), and a private ticket channel is created.

### 4. Set up the stats channel

Creates two pinned messages in a dedicated stats channel:
- A live **open tickets & staff loads** panel
- An **interaction leaderboard** with buttons to cycle between Today / Week / Month / All-Time

```
/setup stats channel:<#channel>
```

> Pro tip: Create a dedicated `#ticket-stats` channel that only staff can see. Run this command once per server.

### Managing categories

- **Add more categories:** Run `/setup category` again with a different name.
- **Edit a category:** Run `/setup category` with the same name — it overwrites the previous config.
- **Update questions:** Run `/setup questions` again to replace the question list.
- **Remove a category:** Edit `config.json` directly or implement the future `/setup category delete` command.

---

## Moderator Usage

> All commands below are **slash commands** typed directly in the ticket channel.

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

1. Saves the **entire channel transcript** (every message, including attachments) to the database.
2. Posts the close reason.
3. Updates the stats and leaderboard.
4. Displays a 5-second countdown, then **deletes the channel**.

> The transcript is searchable and viewable later via `/transcript`.

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
@admin3 — 0
```

### Leaderboard

The second pinned message shows a leaderboard of staff interactions. Use the **◀ ▶** buttons to cycle through:

| View | Range |
|------|-------|
| Today | Interactions since midnight UTC |
| This Week | Last 7 days |
| This Month | Last 30 days |
| All Time | Since the bot was set up |

Each staff member's count is the **number of distinct tickets** they've interacted with (claimed, assigned, closed, etc.), including closed tickets.
