#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================================
                           MASTER BOT
===========================================================================
Author             : Moderator007
Latest Commit Hash : a70a8a8
Description        : This bot downloads links from a .TXT file and uploads
                     them to Telegram with metadata extraction, FFmpeg‑generated
                     thumbnails, and real‑time progress updates.
===========================================================================
"""

import os
import re
import sys
import time
import asyncio
import requests
import subprocess
import logging
from telethon import TelegramClient, events
import aiohttp
from moviepy.editor import VideoFileClip  # To extract video metadata
from telethon.tl.types import DocumentAttributeVideo  # For video attributes

# ---------------------------------------------------------------------------
# Import configuration variables from vars module
# ---------------------------------------------------------------------------
from vars import API_ID, API_HASH, BOT_TOKEN

# ---------------------------------------------------------------------------
# Import custom helper functions for downloading operations
# ---------------------------------------------------------------------------
import core as helper  # Assumes helper.download_video() and helper.download() exist

# ---------------------------------------------------------------------------
# Import external fast_upload function from devgagantools library
# Attempt to import fast_upload; if not found, fallback to upload_file as fast_upload
# ---------------------------------------------------------------------------
try:
    from devgagantools.spylib import fast_upload
except ImportError:
    from devgagantools.spylib import upload_file as fast_upload

# ---------------------------------------------------------------------------
# Set up logging configuration
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telethon")

# ---------------------------------------------------------------------------
# Initialize the Telethon client
# ---------------------------------------------------------------------------
bot = TelegramClient("bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# =============================================================================
#                           HELPER FUNCTIONS
# =============================================================================
def human_readable(size, decimal_places=2):
    """
    Convert bytes to a human-readable format.
    
    Args:
        size (int): Size in bytes.
        decimal_places (int): Number of decimal places to round to.
        
    Returns:
        str: Human-readable size.
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.{decimal_places}f}{unit}"
        size /= 1024
    return f"{size:.{decimal_places}f}PB"

def format_eta(seconds):
    """Format seconds as HH:MM:SS."""
    return time.strftime("%H:%M:%S", time.gmtime(seconds))

def generate_thumbnail(video_file, thumbnail_path, time_offset="00:00:01.000"):
    """
    Generate a thumbnail image from a video file using FFmpeg.

    Args:
        video_file (str): Path to the source video file.
        thumbnail_path (str): Path where the thumbnail image will be saved.
        time_offset (str): Timestamp offset (HH:MM:SS.mmm) to capture the thumbnail.

    Returns:
        str or None: Returns the thumbnail path if successful, otherwise None.
    """
    ffmpeg_executable = "ffmpeg"  # Change to absolute path if necessary (e.g., '/usr/bin/ffmpeg')
    command = [
        ffmpeg_executable,
        "-i", video_file,
        "-ss", time_offset,
        "-vframes", "1",
        thumbnail_path,
        "-y"  # Overwrite output file if it exists
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return thumbnail_path
    except subprocess.CalledProcessError as e:
        log.error(f"Thumbnail generation failed: {e}")
        return None

# =============================================================================
#                           TELEGRAM BOT HANDLERS
# =============================================================================

@bot.on(events.NewMessage(pattern=r'^/start'))
async def start_handler(event):
    """
    /start command handler.
    
    Sends a welcome message and instructions.
    """
    welcome_message = (
        f"<b>Hello {event.sender.first_name} 👋</b>\n\n"
        "I am a bot that downloads links from your <b>.TXT</b> file and uploads them to Telegram.\n"
        "To use me, send /upload and follow the steps.\n"
        "Send /stop to abort any ongoing task."
    )
    msg = await event.reply(welcome_message)
    await asyncio.sleep(5)
    await bot.delete_messages(event.chat_id, msg.id)

@bot.on(events.NewMessage(pattern=r'^/stop'))
async def stop_handler(event):
    """
    /stop command handler.
    
    Stops the bot by restarting the script.
    """
    await event.reply("**Stopped** 🚦")
    os.execl(sys.executable, sys.executable, *sys.argv)

@bot.on(events.NewMessage(pattern=r'^/upload'))
async def upload_handler(event):
    """
    /upload command handler.
    
    Processes a .TXT file with download links, prompts for additional inputs,
    downloads each file, and uploads it to Telegram using fast_upload.
    """
    async with bot.conversation(event.chat_id) as conv:
        # -------------------------------------------------------------------
        # STEP 1: Ask for the TXT file containing the links
        # -------------------------------------------------------------------
        q1 = await conv.send_message("Send TXT file ⚡️")
        txt_msg = await conv.get_response()
        await bot.delete_messages(event.chat_id, [q1.id, txt_msg.id])
        txt_path = await bot.download_media(txt_msg)
        try:
            with open(txt_path, "r") as f:
                content = f.read()
            lines = content.splitlines()
            # Each non-empty line is expected to be in a protocol://URL format
            links = [line.split("://", 1) for line in lines if line.strip()]
            os.remove(txt_path)
        except Exception as e:
            err_msg = await conv.send_message("**Invalid file input.**")
            await asyncio.sleep(3)
            await bot.delete_messages(event.chat_id, err_msg.id)
            os.remove(txt_path)
            return

        # -------------------------------------------------------------------
        # STEP 2: Ask if password-protected links exist and get the PW token
        # -------------------------------------------------------------------
        q2 = await conv.send_message(
            "Are there any password-protected links in this file? "
            "If yes, send the PW token. If not, type 'no'."
        )
        pw_msg = await conv.get_response()
        pw_token = pw_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q2.id, pw_msg.id])

        # -------------------------------------------------------------------
        # STEP 3: Ask for the starting link index
        # -------------------------------------------------------------------
        q3 = await conv.send_message(
            f"**Total links found:** **{len(links)}**\n\n"
            "Send a number indicating from which link you want to start downloading (e.g. 1)."
        )
        start_msg = await conv.get_response()
        try:
            start_index = int(start_msg.text.strip())
        except Exception:
            start_index = 1
        await bot.delete_messages(event.chat_id, [q3.id, start_msg.id])

        # -------------------------------------------------------------------
        # STEP 4: Ask for the batch name
        # -------------------------------------------------------------------
        q4 = await conv.send_message("Now send me your batch name:")
        batch_msg = await conv.get_response()
        batch_name = batch_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q4.id, batch_msg.id])

        # -------------------------------------------------------------------
        # STEP 5: Ask for desired video resolution
        # -------------------------------------------------------------------
        q5 = await conv.send_message("Enter resolution (choose: 144, 240, 360, 480, 720, 1080):")
        res_msg = await conv.get_response()
        raw_res = res_msg.text.strip()
        await bot.delete_messages(event.chat_id, [q5.id, res_msg.id])
        if raw_res == "144":
            res = "256x144"
        elif raw_res == "240":
            res = "426x240"
        elif raw_res == "360":
            res = "640x360"
        elif raw_res == "480":
            res = "854x480"
        elif raw_res == "720":
            res = "1280x720"
        elif raw_res == "1080":
            res = "1920x1080"
        else:
            res = "UN"

        # -------------------------------------------------------------------
        # STEP 6: Ask for a caption to be used on the uploaded file
        # -------------------------------------------------------------------
        q6 = await conv.send_message("Now enter a caption for your uploaded file:")
        caption_msg = await conv.get_response()
        caption_input = caption_msg.text.strip()
        highlighter = "️ ⁪⁬⁮⁮⁮"  # Custom highlighter string if needed
        caption = highlighter if caption_input == 'Robin' else caption_input
        await bot.delete_messages(event.chat_id, [q6.id, caption_msg.id])

        # -------------------------------------------------------------------
        # STEP 7: Ask for a thumbnail image (optional)
        # -------------------------------------------------------------------
        q7 = await conv.send_message(
            "Send a thumbnail image for this batch (or type 'no' to skip and let Telegram auto‑generate one):"
        )
        thumb_msg = await conv.get_response()
        await bot.delete_messages(event.chat_id, [q7.id, thumb_msg.id])
        if thumb_msg.media:
            thumb_path = await bot.download_media(thumb_msg)
        else:
            thumb_path = None
            if thumb_msg.text.strip().lower() != "no":
                thumb_path = None
        # 'batch_thumb' will be used for all files if provided; otherwise we generate one per file
        batch_thumb = thumb_path

        # -------------------------------------------------------------------
        # STATUS: Notify user of processing start
        # -------------------------------------------------------------------
        status_msg = await conv.send_message("Processing your links...")

        # =============================================================================
        # PROCESS EACH LINK
        # =============================================================================
        for i in range(start_index - 1, len(links)):
            # -------------------------------------------------------------------
            # Reconstruct the URL from the provided link parts
            # -------------------------------------------------------------------
            link_protocol, link_body = links[i]
            V = link_body.replace("file/d/", "uc?export=download&id=") \
                         .replace("www.youtube-nocookie.com/embed", "youtu.be") \
                         .replace("?modestbranding=1", "") \
                         .replace("/view?usp=sharing", "")
            url = "https://" + V

            # -------------------------------------------------------------------
            # Special URL processing for specific providers
            # -------------------------------------------------------------------
            if "visionias" in url:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers={
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                                      'image/avif,image/webp,image/apng,*/*;q=0.8',
                            'User-Agent': 'Mozilla/5.0'
                        }
                    ) as resp:
                        text = await resp.text()
                        m = re.search(r"(https://.*?playlist\.m3u8.*?)\"", text)
                        if m:
                            url = m.group(1)
            elif 'videos.classplusapp' in url:
                api_url = "https://api.classplusapp.com/cams/uploader/video/jw-signed-url?url=" + url
                response = requests.get(api_url, headers={'x-access-token': 'TOKEN'})
                try:
                    url = response.json()['url']
                except Exception as e:
                    log.error(f"Error processing Classplusapp URL: {e}")
            elif '/master.mpd' in url:
                # -------------------------------------------------------------------
                # Updated handling for master.mpd URLs:
                # For Telegram Download Bot, always use the anonymouspwplayer endpoint.
                # -------------------------------------------------------------------
                url = f"https://anonymouspwplayer-b99f57957198.herokuapp.com/pw?url={url}?token={pw_token}"

            # -------------------------------------------------------------------
            # Construct a safe file name based on the link title
            # -------------------------------------------------------------------
            name1 = links[i][0]
            name1 = name1.replace("\t", "").replace(":", "").replace("/", "") \
                         .replace("+", "").replace("#", "").replace("|", "") \
                         .replace("@", "").replace("*", "").replace(".", "") \
                         .replace("https", "").replace("http", "").strip()
            file_name = f'{str(i+1).zfill(3)}) {name1[:60]}'

            # -------------------------------------------------------------------
            # Determine the yt-dlp format template based on URL type
            # -------------------------------------------------------------------
            if "youtu" in url:
                ytf = f"b[height<={raw_res}][ext=mp4]/bv[height<={raw_res}][ext=mp4]+ba[ext=m4a]/b[ext=mp4]"
            else:
                ytf = f"b[height<={raw_res}]/bv[height<={raw_res}]+ba/b/bv+ba"

            # -------------------------------------------------------------------
            # Build the yt-dlp command for video downloading
            # -------------------------------------------------------------------
            if "jw-prod" in url:
                cmd = (
                    f'yt-dlp --external-downloader aria2c '
                    f'--external-downloader-args "-x 16 -s 16 -k 1M --timeout=120 --connect-timeout=120 '
                    f'--max-download-limit=0 --max-overall-download-limit=0 '
                    f'--enable-http-pipelining=true --file-allocation=falloc" '
                    f'-o "{file_name}.mp4" "{url}"'
                )
            else:
                cmd = (
                    f'yt-dlp --external-downloader aria2c '
                    f'--external-downloader-args "-x 16 -s 16 -k 1M --timeout=120 --connect-timeout=120 '
                    f'--max-download-limit=0 --max-overall-download-limit=0 '
                    f'--enable-http-pipelining=true --file-allocation=falloc" '
                    f'-f "{ytf}" "{url}" -o "{file_name}.mp4"'
                )

            # -------------------------------------------------------------------
            # Try downloading and then uploading the file
            # -------------------------------------------------------------------
            try:
                cc = (
                    f"**{str(i+1).zfill(3)}**. {name1}{caption}.mkv\n"
                    f"**Batch Name »** {batch_name}\n"
                    f"**Downloaded By :** TechMon ❤️‍🔥 @TechMonX"
                )
                cc1 = (
                    f"**{str(i+1).zfill(3)}**. {name1}{caption}.pdf\n"
                    f"**Batch Name »** {batch_name}\n"
                    f"**Downloaded By :** TechMon ❤️‍🔥 @TechMonX"
                )

                # ----------------------------------------------------------------
                # Special handling for Drive and PDF links
                # ----------------------------------------------------------------
                if "drive" in url:
                    try:
                        ka = await helper.download(url, file_name)
                        await conv.send_message("Uploading document...")
                        await bot.send_file(event.chat_id, file=ka, caption=cc1)
                        os.remove(ka)
                        await asyncio.sleep(1)
                    except Exception as e:
                        await conv.send_message(str(e))
                        await asyncio.sleep(5)
                        continue
                elif ".pdf" in url:
                    try:
                        cmd_pdf = (
                            f'yt-dlp --external-downloader aria2c '
                            f'--external-downloader-args "-x 16 -s 16 -k 1M --timeout=120 --connect-timeout=120 '
                            f'--max-download-limit=0 --max-overall-download-limit=0 '
                            f'--enable-http-pipelining=true --file-allocation=falloc" '
                            f'-o "{file_name}.pdf" "{url}"'
                        )
                        download_cmd = f"{cmd_pdf} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        await bot.send_file(event.chat_id, file=f'{file_name}.pdf', caption=cc1)
                        os.remove(f'{file_name}.pdf')
                        await asyncio.sleep(1)
                    except Exception as e:
                        await conv.send_message(str(e))
                        await asyncio.sleep(5)
                        continue
                else:
                    # ----------------------------------------------------------------
                    # Download the video using helper.download_video
                    # ----------------------------------------------------------------
                    dl_msg = await conv.send_message(
                        f"**⥥ DOWNLOADING... »**\n\n"
                        f"**Name »** `{file_name}`\n"
                        f"**Quality »** {raw_res}\n\n"
                        f"**URL »** `{url}`"
                    )
                    res_file = await helper.download_video(url, cmd, file_name)
                    await bot.delete_messages(event.chat_id, dl_msg.id)

                    # ----------------------------------------------------------------
                    # Extract video metadata with MoviePy
                    # ----------------------------------------------------------------
                    clip = VideoFileClip(res_file)
                    duration = int(clip.duration)
                    width, height = clip.size
                    clip.close()
                    
                    # ----------------------------------------------------------------
                    # If no thumbnail was provided, generate one for this video using FFmpeg
                    # ----------------------------------------------------------------
                    if batch_thumb is None:
                        thumb_file = f"{file_name}_thumb.jpg"
                        generated_thumb = generate_thumbnail(res_file, thumb_file)
                        current_thumb = generated_thumb
                    else:
                        current_thumb = batch_thumb

                    # ----------------------------------------------------------------
                    # UPLOAD WITH PROGRESS CALLBACK using custom progress bar
                    # ----------------------------------------------------------------
                    progress_msg = await conv.send_message("Uploading file... 0%")
                    last_percent = 0
                    last_time = time.time()
                    last_bytes = 0

                    async def progress_callback(current, total):
                        nonlocal last_percent, last_time, last_bytes
                        percent = (current / total) * 100
                        if percent - last_percent >= 5 or current == total:
                            now = time.time()
                            dt = now - last_time
                            speed = (current - last_bytes) / dt if dt > 0 else 0
                            speed_str = human_readable(speed) + "/s"
                            # Create a progress bar with 20 segments
                            bar_length = 20
                            filled_length = int(bar_length * current // total)
                            progress_bar = "█" * filled_length + "░" * (bar_length - filled_length)
                            perc_str = f"{percent:.2f}%"
                            cur_str = human_readable(current)
                            tot_str = human_readable(total)
                            if speed > 0:
                                eta_seconds = (total - current) / speed
                                eta = format_eta(eta_seconds)
                            else:
                                eta = "Calculating..."
                            text = (
                                f"<b>\n"
                                f" ╭──⌯════🆄︎ᴘʟᴏᴀᴅɪɴɢ⬆️⬆️═════⌯──╮ \n"
                                f"├⚡ {progress_bar}|﹝{perc_str}﹞ \n"
                                f"├🚀 Speed » {speed_str} \n"
                                f"├📟 Processed » {cur_str}\n"
                                f"├🧲 Size - ETA » {tot_str} - {eta} \n"
                                f"├🤖 By » TechMon\n"
                                f"╰─═══ ✪ TechMon ✪ ═══─╯\n"
                                f"</b>"
                            )
                            try:
                                await bot.edit_message(event.chat_id, progress_msg.id, text)
                            except Exception as ex:
                                log.error(f"Progress update failed: {ex}")
                            last_percent = percent
                            last_time = now
                            last_bytes = current

                    with open(res_file, "rb") as file_obj:
                        uploaded_file = await fast_upload(bot, file_obj, progress_callback=progress_callback)
                    await bot.delete_messages(event.chat_id, progress_msg.id)

                    # ----------------------------------------------------------------
                    # Set the uploaded file's name and add video attributes
                    # ----------------------------------------------------------------
                    uploaded_file.name = f"{file_name}.mp4"
                    attributes = [DocumentAttributeVideo(duration, w=width, h=height, supports_streaming=True)]

                    # ----------------------------------------------------------------
                    # Send the uploaded file with proper metadata and thumbnail
                    # ----------------------------------------------------------------
                    await bot.send_file(
                        event.chat_id,
                        file=uploaded_file,
                        caption=cc,
                        supports_streaming=True,
                        attributes=attributes,
                        thumb=current_thumb
                    )
                    await asyncio.sleep(1)

            except Exception as e:
                error_text = (
                    f"**Downloading Interrupted**\n{str(e)}\n"
                    f"**Name »** {file_name}\n"
                    f"**URL »** `{url}`"
                )
                await conv.send_message(error_text)
                continue

        # =============================================================================
        # End of link processing
        # =============================================================================
        await conv.send_message("**Done Boss 😎**")
        await bot.delete_messages(event.chat_id, status_msg.id)

        # -------------------------------------------------------------------
        # Clean up: Remove thumbnail file if provided/generated
        # -------------------------------------------------------------------
        if batch_thumb is not None and os.path.exists(batch_thumb):
            os.remove(batch_thumb)

# =============================================================================
#                           MAIN ENTRY POINT
# =============================================================================
def main():
    print("Bot is running... (Commit a70a8a8)")
    bot.run_until_disconnected()

if __name__ == '__main__':
    main()
