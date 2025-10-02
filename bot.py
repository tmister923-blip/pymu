import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os
import yt_dlp as youtube_dl
import asyncio
import logging
from aiohttp import web

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Load environment variables (for local development)
try:
    load_dotenv()
except:
    pass  # In production, environment variables are set by the platform

# Get Discord token from environment
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    logging.error("DISCORD_TOKEN environment variable not found!")
    exit(1)

# Get port from environment (Render.com uses PORT env var)
PORT = int(os.getenv('PORT', 10000))

# Cấu hình bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='$', intents=intents)

# Kiểm tra và khởi tạo CommandTree
if not hasattr(bot, 'tree'):
    bot.tree = app_commands.CommandTree(bot)

# Hàng đợi và âm lượng cho mỗi server
queues = {}  # {guild_id: [song_info]}
volumes = {}  # {guild_id: volume_level (0.0-2.0)}

# Hook khi bot ready
@bot.event
async def on_ready():
    logging.info(f'{bot.user} đã online!')
    try:
        synced = await bot.tree.sync()
        logging.info(f"Đã đồng bộ {len(synced)} lệnh slash!")
    except Exception as e:
        logging.error(f"Lỗi đồng bộ: {e}")

# Hàm phát bài tiếp theo
async def play_next(ctx_or_interaction):
    guild_id = ctx_or_interaction.guild.id if hasattr(ctx_or_interaction, 'guild') else ctx_or_interaction.interaction.guild.id
    voice_client = ctx_or_interaction.guild.voice_client if hasattr(ctx_or_interaction, 'guild') else ctx_or_interaction.interaction.guild.voice_client
    
    if not voice_client:
        logging.error(f"Bot không ở trong voice channel (Guild ID: {guild_id})")
        if hasattr(ctx_or_interaction, 'send'):
            await ctx_or_interaction.send('Bot không ở trong voice channel!')
        else:
            await ctx_or_interaction.interaction.followup.send('Bot không ở trong voice channel!')
        return

    if guild_id in queues and queues[guild_id]:
        info = queues[guild_id].pop(0)
        try:
            # Lấy URL luồng âm thanh
            url2 = info.get('url') or info['formats'][0].get('url')
            if not url2:
                raise ValueError("Không tìm thấy URL âm thanh hợp lệ")
            logging.info(f"Chuẩn bị phát: {info['title']} ({url2})")
            source = discord.FFmpegPCMAudio(url2, **{
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn'
            })
            
            # Áp dụng âm lượng
            volume = volumes.get(guild_id, 1.0)
            source = discord.PCMVolumeTransformer(source, volume=volume)
            
            voice_client.play(source, after=lambda e: bot.loop.create_task(play_next(ctx_or_interaction)))
            
            logging.info(f"Đang phát: {info['title']}")
            if hasattr(ctx_or_interaction, 'send'):
                await ctx_or_interaction.send(f'Đang phát: {info["title"]}')
            else:
                await ctx_or_interaction.interaction.followup.send(f'Đang phát: {info["title"]}')
        except Exception as e:
            logging.error(f"Lỗi khi phát bài hát {info['title']}: {e}")
            if hasattr(ctx_or_interaction, 'send'):
                await ctx_or_interaction.send(f'Lỗi khi phát bài hát: {e}')
            else:
                await ctx_or_interaction.interaction.followup.send(f'Lỗi khi phát bài hát: {e}')
            await play_next(ctx_or_interaction)  # Thử bài tiếp theo
    else:
        logging.info(f"Hàng đợi rỗng trong server {guild_id}")
        if hasattr(ctx_or_interaction, 'send'):
            await ctx_or_interaction.send('Hàng đợi rỗng!')
        else:
            await ctx_or_interaction.interaction.followup.send('Hàng đợi rỗng!')

# Lệnh join (prefix)
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        try:
            await channel.connect()
            await ctx.send(f'Joined {channel.name}')
            logging.info(f"Bot đã join voice channel: {channel.name} (Guild ID: {ctx.guild.id})")
        except Exception as e:
            logging.error(f"Lỗi khi join voice channel: {e}")
            await ctx.send(f'Lỗi khi join voice channel: {e}')
    else:
        await ctx.send('Bạn cần join voice channel trước!')

# Lệnh join (slash)
@bot.tree.command(name="join", description="Bot vào voice channel của bạn")
async def slash_join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        try:
            await channel.connect()
            await interaction.response.send_message(f'Joined {channel.name}')
            logging.info(f"Bot đã join voice channel: {channel.name} (Guild ID: {interaction.guild.id})")
        except Exception as e:
            logging.error(f"Lỗi khi join voice channel: {e}")
            await interaction.response.send_message(f'Lỗi khi join voice channel: {e}')
    else:
        await interaction.response.send_message('Bạn cần join voice channel trước!')

# Lệnh phát nhạc (prefix)
@bot.command()
async def play(ctx, url: str):
    if not ctx.voice_client:
        await ctx.invoke(bot.get_command('join'))
        if not ctx.voice_client:
            return
    
    async with ctx.typing():
        # Try multiple yt-dlp configurations
        ydl_configs = [
            # Configuration 1: Basic with search fallback
            {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'default_search': 'ytsearch',  # Force search mode
                'extractaudio': True,
                'audioformat': 'mp3',
                'source_address': '0.0.0.0',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                },
                'extractor_args': {
                    'youtube': {
                        'skip': ['hls', 'dash'],
                        'player_skip': ['configs', 'webpage'],
                    }
                }
            },
            # Configuration 2: Alternative with age gate bypass
            {
                'format': 'worst[ext=mp4]/worst',
                'quiet': True,
                'no_warnings': True,
                'default_search': 'ytsearch',
                'age_limit': 99,
                'source_address': '0.0.0.0',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
                }
            },
            # Configuration 3: Minimalist approach
            {
                'format': 'bestaudio',
                'quiet': True,
                'default_search': 'ytsearch',
                'extract_flat': False,
                'writethumbnail': False,
                'writeinfojson': False,
            }
        ]
        
        # If URL contains youtube, convert to search query instead
        if 'youtube.com' in url or 'youtu.be' in url:
            # Extract title from URL or use video ID as search term
            video_id = None
            if 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[1].split('?')[0]
            elif 'v=' in url:
                video_id = url.split('v=')[1].split('&')[0]
            
            if video_id:
                # Try to search for the video instead of direct URL
                search_url = f"ytsearch1:{video_id}"
                await ctx.send(f"⚠️ Converting YouTube URL to search to avoid bot detection...")
            else:
                search_url = f"ytsearch1:{url}"
        else:
            # For non-YouTube URLs or search terms
            if not url.startswith(('http://', 'https://')):
                search_url = f"ytsearch1:{url}"
            else:
                search_url = url
        
        ydl_opts = ydl_configs[0]  # Start with first config
        
        info = None
        last_error = None
        
        # Try multiple configurations and approaches
        for config_idx, ydl_config in enumerate(ydl_configs):
            try:
                with youtube_dl.YoutubeDL(ydl_config) as ydl:
                    logging.info(f"Trying configuration {config_idx + 1} with: {search_url}")
                    info = await asyncio.to_thread(ydl.extract_info, search_url, download=False)
                    
                    # If we get results, break out of the config loop
                    if info:
                        if 'entries' in info and info['entries']:
                            info = info['entries'][0]  # Get first search result
                        break
                        
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                logging.warning(f"Configuration {config_idx + 1} failed: {e}")
                
                # If this is a bot detection error, try next configuration
                if any(phrase in error_msg for phrase in ['sign in', 'bot', 'cookies', 'private']):
                    continue
                # If it's a different error, might be worth retrying with same config
                elif config_idx == 0:  # Only retry on first config
                    await asyncio.sleep(2)
                    continue
        
        # If all configurations failed, try one last desperate search attempt
        if not info and not url.startswith('ytsearch'):
            try:
                # Extract meaningful keywords from URL or use as-is
                if 'youtube.com' in url or 'youtu.be' in url:
                    # For YouTube URLs that failed, try searching with video ID
                    video_id = None
                    if 'youtu.be/' in url:
                        video_id = url.split('youtu.be/')[1].split('?')[0]
                    elif 'v=' in url:
                        video_id = url.split('v=')[1].split('&')[0]
                    
                    if video_id:
                        desperate_search = f"ytsearch3:{video_id}"  # Get top 3 results
                        logging.info(f"Desperate search attempt: {desperate_search}")
                        
                        with youtube_dl.YoutubeDL({'quiet': True, 'default_search': 'ytsearch'}) as ydl:
                            info = await asyncio.to_thread(ydl.extract_info, desperate_search, download=False)
                            if info and 'entries' in info and info['entries']:
                                info = info['entries'][0]
            except Exception as desperate_error:
                logging.error(f"Desperate search also failed: {desperate_error}")
        
        if not info:
            raise last_error or Exception("All extraction methods failed")
        
        # If we got here, we have valid info
        try:
            guild_id = ctx.guild.id
            if guild_id not in queues:
                queues[guild_id] = []
            
            # Add to queue
            queues[guild_id].append(info)
            title = info.get('title', 'Unknown Track')
            logging.info(f"Đã thêm bài hát vào hàng đợi: {title} (Guild ID: {guild_id})")
            
            if not ctx.voice_client.is_playing():
                await play_next(ctx)
            else:
                await ctx.send(f'✅ Đã thêm vào hàng đợi: **{title}**')
                
        except Exception as queue_error:
            logging.error(f"Error adding to queue: {queue_error}")
            await ctx.send(f'Error adding to queue: {queue_error}')
            
    except Exception as e:
        error_msg = str(e).lower()
        logging.error(f"Lỗi khi xử lý URL {url}: {e}")
        
        if any(phrase in error_msg for phrase in ['sign in', 'bot', 'cookies']):
            await ctx.send('⚠️ **YouTube Bot Detection Error!**\n'
                          'Try these alternatives:\n'
                          '• Use search terms instead: `$play never gonna give you up`\n'
                          '• Use song + artist: `$play bohemian rhapsody queen`\n'
                          '• Try a different video if using URL')
        elif 'private' in error_msg or 'unavailable' in error_msg:
            await ctx.send('❌ **Video unavailable** - it might be private, deleted, or region-blocked. Try searching for the song instead!')
        else:
            await ctx.send(f'❌ **Error**: {str(e)[:100]}...'  if len(str(e)) > 100 else f'❌ **Error**: {e}')

# Lệnh phát nhạc (slash) - Improved version
@bot.tree.command(name="play", description="Play music from YouTube URL or search")
@app_commands.describe(url="YouTube URL or search terms")
async def slash_play(interaction: discord.Interaction, url: str):
    if not interaction.guild.voice_client:
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            try:
                await channel.connect()
                logging.info(f"Bot đã join voice channel: {channel.name} (Guild ID: {interaction.guild.id})")
            except Exception as e:
                logging.error(f"Lỗi khi join voice channel: {e}")
                await interaction.response.send_message(f'Lỗi khi join voice channel: {e}')
                return
        else:
            await interaction.response.send_message('Bạn cần join voice channel trước!')
            return
    
    await interaction.response.defer()
    
    # Same improved config as prefix command
    ydl_configs = [
        {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'extractaudio': True,
            'audioformat': 'mp3',
            'source_address': '0.0.0.0',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            'extractor_args': {
                'youtube': {
                    'skip': ['hls', 'dash'],
                    'player_skip': ['configs', 'webpage'],
                }
            }
        },
        {
            'format': 'worst[ext=mp4]/worst',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'age_limit': 99,
            'source_address': '0.0.0.0',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
            }
        },
        {
            'format': 'bestaudio',
            'quiet': True,
            'default_search': 'ytsearch',
            'extract_flat': False,
            'writethumbnail': False,
            'writeinfojson': False,
        }
    ]
    
    # Convert YouTube URLs to search
    if 'youtube.com' in url or 'youtu.be' in url:
        video_id = None
        if 'youtu.be/' in url:
            video_id = url.split('youtu.be/')[1].split('?')[0]
        elif 'v=' in url:
            video_id = url.split('v=')[1].split('&')[0]
        
        if video_id:
            search_url = f"ytsearch1:{video_id}"
            await interaction.edit_original_response(content="⚠️ Converting YouTube URL to search to avoid bot detection...")
        else:
            search_url = f"ytsearch1:{url}"
    else:
        if not url.startswith(('http://', 'https://')):
            search_url = f"ytsearch1:{url}"
        else:
            search_url = url
    
    # Try extraction with multiple configs
    info = None
    last_error = None
    
    try:
        for config_idx, ydl_config in enumerate(ydl_configs):
            try:
                with youtube_dl.YoutubeDL(ydl_config) as ydl:
                    logging.info(f"Slash command trying configuration {config_idx + 1} with: {search_url}")
                    info = await asyncio.to_thread(ydl.extract_info, search_url, download=False)
                    
                    if info:
                        if 'entries' in info and info['entries']:
                            info = info['entries'][0]
                        break
                        
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                logging.warning(f"Slash config {config_idx + 1} failed: {e}")
                
                if any(phrase in error_msg for phrase in ['sign in', 'bot', 'cookies', 'private']):
                    continue
                elif config_idx == 0:
                    await asyncio.sleep(2)
                    continue
        
        if not info:
            raise last_error or Exception("All extraction methods failed")
        
        # Add to queue
        guild_id = interaction.guild.id
        if guild_id not in queues:
            queues[guild_id] = []
        
        queues[guild_id].append(info)
        title = info.get('title', 'Unknown Track')
        logging.info(f"Đã thêm bài hát vào hàng đợi: {title} (Guild ID: {guild_id})")
        
        if not interaction.guild.voice_client.is_playing():
            await play_next(interaction)
        else:
            await interaction.edit_original_response(content=f'✅ Đã thêm vào hàng đợi: **{title}**')
            
    except Exception as e:
        error_msg = str(e).lower()
        logging.error(f"Slash command lỗi: {e}")
        
        if any(phrase in error_msg for phrase in ['sign in', 'bot', 'cookies']):
            await interaction.edit_original_response(content='⚠️ **YouTube Bot Detection Error!**\n'
                                                   'Try these alternatives:\n'
                                                   '• Use search terms: `/play never gonna give you up`\n'
                                                   '• Use song + artist: `/play bohemian rhapsody queen`\n'
                                                   '• Try a different video if using URL')
        elif 'private' in error_msg or 'unavailable' in error_msg:
            await interaction.edit_original_response(content='❌ **Video unavailable** - Try searching for the song instead!')
        else:
            await interaction.edit_original_response(content=f'❌ **Error**: {str(e)[:100]}...' if len(str(e)) > 100 else f'❌ **Error**: {e}')

# Lệnh hiển thị hàng đợi (prefix)
@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues and queues[guild_id]:
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queues[guild_id]))
        await ctx.send(f'**Hàng đợi hiện tại**:\n{queue_list}')
        logging.info(f"Hiển thị hàng đợi trong server {guild_id}")
    else:
        await ctx.send('Hàng đợi rỗng!')
        logging.info(f"Hàng đợi rỗng trong server {guild_id}")

# Lệnh hiển thị hàng đợi (slash)
@bot.tree.command(name="queue", description="Hiển thị danh sách hàng đợi")
async def slash_queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in queues and queues[guild_id]:
        queue_list = "\n".join(f"{i+1}. {song['title']}" for i, song in enumerate(queues[guild_id]))
        await interaction.response.send_message(f'**Hàng đợi hiện tại**:\n{queue_list}')
        logging.info(f"Hiển thị hàng đợi trong server {guild_id}")
    else:
        await interaction.response.send_message('Hàng đợi rỗng!')
        logging.info(f"Hàng đợi rỗng trong server {guild_id}")

# Lệnh điều chỉnh âm lượng (prefix)
@bot.command()
async def volume(ctx, volume: int):
    if not ctx.voice_client:
        await ctx.send('Bot chưa ở trong voice channel!')
        logging.error(f"Không tìm thấy voice client trong server {ctx.guild.id}")
        return
    
    if 0 <= volume <= 200:
        volumes[ctx.guild.id] = volume / 100.0
        if ctx.voice_client.source:
            ctx.voice_client.source.volume = volume / 100.0
        await ctx.send(f'Âm lượng được đặt thành {volume}%')
        logging.info(f"Đã đặt âm lượng cho server {ctx.guild.id}: {volume}%")
    else:
        await ctx.send('Âm lượng phải từ 0 đến 200!')
        logging.warning(f"Âm lượng không hợp lệ: {volume} (Server ID: {ctx.guild.id})")

# Lệnh điều chỉnh âm lượng (slash)
@bot.tree.command(name="volume", description="Điều chỉnh âm lượng (0-200%)")
@app_commands.describe(volume="Mức âm lượng (0-200)")
async def slash_volume(interaction: discord.Interaction, volume: int):
    if not interaction.guild.voice_client:
        await interaction.response.send_message('Bot chưa ở trong voice channel!')
        logging.error(f"Không tìm thấy voice client trong server {interaction.guild.id}")
        return
    
    if 0 <= volume <= 200:
        volumes[interaction.guild.id] = volume / 100.0
        if interaction.guild.voice_client.source:
            interaction.guild.voice_client.source.volume = volume / 100.0
        await interaction.response.send_message(f'Âm lượng được đặt thành {volume}%')
        logging.info(f"Đã đặt âm lượng cho server {interaction.guild.id}: {volume}%")
    else:
        await interaction.response.send_message('Âm lượng phải từ 0 đến 200!')
        logging.warning(f"Âm lượng không hợp lệ: {volume} (Server ID: {interaction.guild.id})")

# Lệnh tạm dừng (prefix)
@bot.command()
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send('Đã pause!')
        logging.info(f"Đã tạm dừng nhạc trong server {ctx.guild.id}")
    else:
        await ctx.send('Không có nhạc đang phát!')
        logging.info(f"Không có nhạc để tạm dừng trong server {ctx.guild.id}")

# Lệnh tạm dừng (slash)
@bot.tree.command(name="pause", description="Tạm dừng nhạc đang phát")
async def slash_pause(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        await interaction.response.send_message('Đã pause!')
        logging.info(f"Đã tạm dừng nhạc trong server {interaction.guild.id}")
    else:
        await interaction.response.send_message('Không có nhạc đang phát!')
        logging.info(f"Không có nhạc để tạm dừng trong server {interaction.guild.id}")

# Lệnh tiếp tục (prefix)
@bot.command()
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send('Đã resume!')
        logging.info(f"Đã tiếp tục nhạc trong server {ctx.guild.id}")
    else:
        await ctx.send('Không có nhạc nào bị tạm dừng!')
        logging.info(f"Không có nhạc để tiếp tục trong server {ctx.guild.id}")

# Lệnh tiếp tục (slash)
@bot.tree.command(name="resume", description="Tiếp tục nhạc đã tạm dừng")
async def slash_resume(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        await interaction.response.send_message('Đã resume!')
        logging.info(f"Đã tiếp tục nhạc trong server {interaction.guild.id}")
    else:
        await interaction.response.send_message('Không có nhạc nào bị tạm dừng!')
        logging.info(f"Không có nhạc để tiếp tục trong server {interaction.guild.id}")

# Lệnh dừng (prefix)
@bot.command()
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        queues[ctx.guild.id] = []  # Xóa hàng đợi
        await ctx.send('Đã stop và xóa hàng đợi!')
        logging.info(f"Đã dừng nhạc và xóa hàng đợi trong server {ctx.guild.id}")
    else:
        await ctx.send('Không có nhạc đang phát!')
        logging.info(f"Không có nhạc để dừng trong server {ctx.guild.id}")

# Lệnh dừng (slash)
@bot.tree.command(name="stop", description="Dừng phát nhạc và xóa hàng đợi")
async def slash_stop(interaction: discord.Interaction):
    if interaction.guild.voice_client and interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.stop()
        queues[interaction.guild.id] = []
        await interaction.response.send_message('Đã stop và xóa hàng đợi!')
        logging.info(f"Đã dừng nhạc và xóa hàng đợi trong server {interaction.guild.id}")
    else:
        await interaction.response.send_message('Không có nhạc đang phát!')
        logging.info(f"Không có nhạc để dừng trong server {interaction.guild.id}")

# Lệnh rời voice (prefix)
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        queues[ctx.guild.id] = []  # Xóa hàng đợi
        await ctx.voice_client.disconnect()
        await ctx.send('Đã leave!')
        logging.info(f"Bot đã rời voice channel trong server {ctx.guild.id}")
    else:
        await ctx.send('Bot không ở trong voice channel!')
        logging.info(f"Bot không ở trong voice channel trong server {ctx.guild.id}")

# Lệnh rời voice (slash)
@bot.tree.command(name="leave", description="Bot rời voice channel")
async def slash_leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        queues[interaction.guild.id] = []
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message('Đã leave!')
        logging.info(f"Bot đã rời voice channel trong server {interaction.guild.id}")
    else:
        await interaction.response.send_message('Bot không ở trong voice channel!')
        logging.info(f"Bot không ở trong voice channel trong server {interaction.guild.id}")

# Create a simple HTTP server to keep the service alive on Render.com
async def handle_health_check(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    app.router.add_get('/health', handle_health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")

# Main function to run both bot and web server
async def main():
    # Start the web server
    await start_web_server()
    
    # Start the bot
    async with bot:
        await bot.start(TOKEN)

# Run the main function
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Bot crashed: {e}")
