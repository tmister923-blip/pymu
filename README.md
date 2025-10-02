# Discord Music Bot

A feature-rich Discord music bot written in Python using [discord.py](https://github.com/Rapptz/discord.py) and [yt-dlp](https://github.com/yt-dlp/yt-dlp). This bot can play music from YouTube, manage queues, control volume, and supports both prefix and slash commands.

## Features

- Play music from YouTube links or search queries
- Playlist support (up to 5 songs per playlist)
- Queue management (view, add, clear)
- Volume control (0-200%)
- Pause, resume, and stop playback
- Join and leave voice channels
- Supports both prefix (`$`) and slash (`/`) commands
- Logging for easier debugging

## Requirements

- Python 3.8+
- [discord.py](https://pypi.org/project/discord.py/) (`pip install -U discord.py`)
- [yt-dlp](https://pypi.org/project/yt-dlp/) (`pip install -U yt-dlp`)
- [python-dotenv](https://pypi.org/project/python-dotenv/) (`pip install -U python-dotenv`)
- FFmpeg (must be installed and in your system PATH)

## Setup

### Local Development

1. **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/discord-music-bot.git
    cd discord-music-bot
    ```

2. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3. **Install FFmpeg:**
    - Windows: Download from [FFmpeg.org](https://ffmpeg.org/) and add to PATH
    - macOS: `brew install ffmpeg`
    - Linux: `sudo apt install ffmpeg`

4. **Create a `.env` file:**
    ```
    DISCORD_TOKEN=your_discord_bot_token_here
    ```

5. **Run the bot:**
    ```bash
    python bot.py
    ```

### Deploy to Render.com (Recommended)

1. **Fork this repository to your GitHub account**

2. **Create a new Web Service on Render.com:**
   - Connect your GitHub repository
   - Choose "Docker" as the runtime
   - Render will automatically detect the Dockerfile

3. **Set Environment Variables in Render Dashboard:**
   - Go to your service settings
   - Add environment variable: `DISCORD_TOKEN` = `your_discord_bot_token_here`

4. **Deploy:**
   - Render will automatically build and deploy your bot
   - FFmpeg is pre-installed in the Docker container
   - The bot will be available 24/7 on Render's free tier

**Note:** Render.com automatically installs FFmpeg in the Docker container, so no manual installation is needed!

## Usage

### Prefix Commands (`$`)

- `$join` — Bot joins your voice channel
- `$play <url or search>` — Play a song or add to queue
- `$queue` — Show current queue
- `$volume <0-200>` — Set playback volume
- `$pause` — Pause playback
- `$resume` — Resume playback
- `$stop` — Stop and clear queue
- `$leave` — Bot leaves the voice channel

### Slash Commands

Type `/` in Discord and select the bot's commands:
- `/join`
- `/play`
- `/queue`
- `/volume`
- `/pause`
- `/resume`
- `/stop`
- `/leave`

## Notes

- The bot will only play audio in voice channels.
- Make sure the bot has permission to join and speak in your voice channel.
- For best results, use the latest version of FFmpeg.

## License

MIT License

---

**Enjoy your music!**