import os
import re
import logging
import time
from dotenv import load_dotenv
import tweepy
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# X (Twitter) API 設定
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN')

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# 初始化 Twitter API
client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """發送歡迎訊息"""
    await update.message.reply_text('歡迎使用 X (Twitter) 媒體下載機器人！\n請傳送 X.com 的貼文連結，我會幫你下載圖片或影片。')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """處理使用者訊息"""
    message = update.message.text
    
    # 檢查是否為 X (Twitter) 連結
    if not re.match(r'https?://(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/\d+', message):
        return  # 如果不是 X 貼文連結，直接返回不回應
    
    try:
        # 從連結中提取推文 ID
        tweet_id = message.split('/')[-1]
        
        # 添加重試機制
        max_retries = 3
        retry_delay = 5  # 秒
        
        for attempt in range(max_retries):
            try:
                # 獲取推文
                tweet = client.get_tweet(tweet_id, expansions=['attachments.media_keys'], 
                                       media_fields=['url', 'preview_image_url', 'variants'])
                
                # 檢查是否有媒體
                if tweet.includes and 'media' in tweet.includes:
                    # 收集所有媒體 URL
                    photo_urls = []
                    video_urls = []
                    
                    for media in tweet.includes['media']:
                        if media.type == 'photo':
                            photo_urls.append(media.url)
                        elif media.type == 'video':
                            # 獲取最高品質的影片
                            if hasattr(media, 'variants'):
                                video_variants = [v for v in media.variants if v.get('content_type') == 'video/mp4']
                                if video_variants:
                                    # 按比特率排序，選擇最高品質
                                    best_video = max(video_variants, key=lambda x: x.get('bit_rate', 0))
                                    video_urls.append(best_video['url'])
                    
                    if photo_urls or video_urls:
                        if len(photo_urls) + len(video_urls) > 1:
                            # 如果有多個媒體，使用 MediaGroup 發送
                            media_group = []
                            # 先添加圖片
                            for url in photo_urls:
                                media_group.append(InputMediaPhoto(url))
                            # 再添加影片
                            for url in video_urls:
                                media_group.append(InputMediaVideo(url))
                            await update.message.reply_media_group(media_group)
                        else:
                            # 如果只有一個媒體，直接發送
                            if photo_urls:
                                await update.message.reply_photo(photo_urls[0])
                            else:
                                await update.message.reply_video(video_urls[0])
                    else:
                        await update.message.reply_text('這則貼文沒有可下載的媒體！')
                    break  # 成功後跳出重試循環
                else:
                    await update.message.reply_text('這則貼文沒有媒體！')
                    break
                    
            except tweepy.TooManyRequests:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1)
                    await update.message.reply_text(f'遇到速率限制，等待 {wait_time} 秒後重試...')
                    time.sleep(wait_time)
                else:
                    await update.message.reply_text('抱歉，目前遇到太多請求，請稍後再試。')
                    break
                    
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text('處理貼文時發生錯誤，請確認連結是否正確。')

def main():
    """啟動機器人"""
    # 建立應用程式
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 加入處理器
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # 啟動機器人
    application.run_polling()

if __name__ == '__main__':
    main() 