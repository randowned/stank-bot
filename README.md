![](static/Stank.gif)

# StankBot

**StankBot** is a custom [BetterDiscord](https://betterdiscord.app/) plugin built for tracking community sticker chains in the [Maphra Discord Server](https://discord.gg/maphra).

It listens to the `#altar` channel for "Stank" sticker chains, awards Stank Points and Punishment Points, and dynamically updates your Server Bio and Nickname when the current or record chain lengths are changed.

## The Game

Players cooperate to build the longest chain of "Stank" stickers in `#altar`. Each **unique user** can contribute once per chain. The chain breaks when anyone posts a non-sticker message.

Rankings are based on **net Stank Points** (earned SP minus punishment points).

| Action | Points |
|---|---|
| Start a new chain (1st sticker after break) | +100 SP, become **Slayer** |
| First-ever sticker contribution (lifetime) | +50 SP bonus |
| Valid unique chain contribution | +25 SP |
| Stank emoji reaction on an ongoing-chain sticker | +5 SP (once per user per sticker) |
| Break the chain | +3× chain length punishment, become **Goat** |
| Chat during a broken chain | +1× chain length punishment |
| Break chain then start the next one | +50 flat punishment (cheating!) |

> **Anti-Cheat:** If the chain breaker immediately starts the next chain, they receive the cheating penalty and **no SP**. The next legitimate contributor inherits the chain starter bonus (+100 SP) and the **Slayer** title.

## Commands

| Command | Description |
|---|---|
| `!stank-board` | The leaderboard (ranked by net SP) |
| `!stank-points` | Your Stank Points and rank |
| `!stank-points <rank>` | Look up a player by rank |
| `!stank-help` | Help message with rules |

### Admin Commands (bot owner only)

| Command | Description |
|---|---|
| `!stank-record-test` | Preview record announcement |
| `!stank-cheater-test` | Preview cheater caught message |
| `!stank-board-reset` | Reset all board data |
| `!stank-board-reload` | Reset and reload from channel history |

## Features

- **Net Score Ranking**: Players ranked by `earned SP - punishment points`. Breakdown shown in `!stank-points`.
- **Chain Tracking**: Tracks the longest unbroken chain of Stank stickers by unique users.
- **Anti-Cheat**: Detects cheaters who break then restart a chain. Bonus transfers to the next legitimate contributor.
- **History Scraping**: Reconstructs chain state from channel history on startup.
- **Dynamic Updates**: Auto-updates your Server Bio and Nickname (e.g. `Username (10/32)`) with current scores.
- **Command Channels**: Configurable allowlist of channel IDs for command auto-replies. DMs always work.
- **Announcement Channels**: Separate allowlist for record-broken and cheater-caught announcements. `!stank-help` works in both command and announcement channels.
- **Logging**: Persistent log file (`StankBot.log`) in the plugins folder with ISO timestamps and session separators.
- **Customization**: Configurable templates for Bio, Nickname, board layout, record announcements, and cheater caught messages.

## Installation

1. Download and install [BetterDiscord](https://betterdiscord.app/).
2. Open Discord → **User Settings** → **BetterDiscord** → **Plugins**.
3. Click **"Open Plugins Folder"** to open `%appdata%\BetterDiscord\plugins`.
4. Drop `StankBot.plugin.js` into the folder.
5. Enable **StankBot** in the Plugins menu.

## Important

> **Self-Bot Warning:** Auto-replying to other users relies on your user account sending API requests without manual input, which goes against Discord's TOS regarding self-bots. Use at your own risk.

---

*Developed for the Maphra Discord Community.*
