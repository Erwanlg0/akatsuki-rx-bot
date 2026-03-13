### Available Commands

| Command          | Description                                      |
|------------------|--------------------------------------------------|
| `/recommend`     | Personalized recommendations based on your profile |
| `/recommend top` | Global top plays from the Akatsuki server       |
| `/profil`        | Complete RX stats (rank, PP, accuracy, grades, clan, etc.) |
| `/top [limit]`   | Personal top plays (1-10 scores)                |
| `/recent [limit]`| Recent scores from the last 24 hours (1-10 scores) |
| `/map <id>`      | Links to a specific beatmap                     |
| `/topline`       | Track Top 1/5/10/20/50/100 PP progression      |
| `/refresh_cache` | Force update of played maps cache               |
| `/clear [limit]` | Delete bot messages (1-50)                      |

## Installation

1. **Clone or download** this bot

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Create a `.env` file**:
```env
DISCORD_TOKEN=your_discord_token_here
DEFAULT_USER=your_akatsuki_username
DEFAULT_USER_ID=your_akatsuki_user_id
```

4. **Run the bot**:
```bash
python main.py
```

## API Structure

The bot uses the official Akatsuki API: `https://akatsuki.gg/api/v1`

### Endpoints Used:
- `/users/full` - Complete profile with RX stats
- `/users/scores/best` - Top plays
- `/users/scores/recent` - Recent scores
- `/leaderboard` - Global leaderboard


