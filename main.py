import asyncio
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)
import io

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Railway: add BOT_TOKEN env var

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Gửi file Excel (.xlsx) chứa danh sách URL trong cột A (header là URL). "
        "Bot sẽ crawl và gửi lại file kết quả Excel."
    )

def crawl_url(url):
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        # Title & Description
        title = soup.find("meta", property="og:title")
        desc = soup.find("meta", property="og:description")
        # Image (cả post và page đều thử lấy cả hai)
        image = soup.find("meta", property="og:image") or soup.find("meta", property="og:image:secure_url")
        # Date
        entry_date = soup.find("time", class_="entry-date published updated")
        updated_time = soup.find("meta", property="og:updated_time")
        # Lấy trường nào có dữ liệu
        date = None
        if entry_date:
            date = entry_date.get("datetime") or entry_date.text
        elif updated_time:
            date = updated_time.get("content")
        return {
            "URL": url,
            "Title": title["content"] if title and "content" in title.attrs else "",
            "Description": desc["content"] if desc and "content" in desc.attrs else "",
            "Date": date or "",
            "Image": image["content"] if image and "content" in image.attrs else ""
        }
    except Exception:
        return {
            "URL": url,
            "Title": "",
            "Description": "",
            "Date": "",
            "Image": ""
        }

async def handle_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_bytes = await file.download_as_bytearray()
    df = pd.read_excel(io.BytesIO(file_bytes))
    if "URL" not in df.columns:
        await update.message.reply_text("File Excel phải có cột tên 'URL'!")
        return
    urls = df["URL"].dropna().tolist()
    result = []
    msg = await update.message.reply_text(f"Đang xử lý {len(urls)} URL...")

    for idx, url in enumerate(urls, 1):
        data = crawl_url(str(url).strip())
        result.append(data)
        if idx % 10 == 0 or idx == len(urls):
            await msg.edit_text(f"Đã xử lý {idx}/{len(urls)} link...")

    result_df = pd.DataFrame(result)
    output = io.BytesIO()
    result_df.to_excel(output, index=False)
    output.seek(0)
    await update.message.reply_document(
        document=InputFile(output, filename="result.xlsx"),
        caption="Kết quả crawl dữ liệu từ các URL."
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.FileExtension("xlsx"), handle_excel))
    print("Bot started!")
    app.run_polling()
