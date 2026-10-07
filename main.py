import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ১. গুগল শিট কনফিগারেশন (Google Sheets Integration)
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

# সার্ভিস অ্যাকাউন্ট ফাইল
SERVICE_ACCOUNT_FILE = 'service_account.json'

try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPE)
    client = gspread.authorize(creds)
    # আপনার গুগল শিট ফাইল এবং শিটের নাম
    sheet = client.open("Facebook k Sheet").sheet1
except Exception as e:
    print(f"Google Sheets Connection Error: {e}")

# ২. বটের কনফিগারেশন ও ডাটা (Bot Configuration)
BOT_TOKEN = "YOUR_BOT_TOKEN" # আপনার টেলিগ্রাম বট টোকেন বসাবেন
REQUIRED_GROUP_ID = "@your_group_username" # আপনার টেলিগ্রাম গ্রুপ/চ্যানেল

RATE_FACEBOOK = 4.0 # ফেসবুক কাজের রেট (টাকা)
RATE_GMAIL = 15.0 # মেইল কাজের রেট (টাকা)
MIN_WITHDRAWAL = 300 # সর্বনিম্ন উইথড্র অ্যামাউন্ট (টাকা)

# ৩. বট সার্ভিসেস এবং কোর ফাংশনসমূহ (Bot Core Functions)

def is_user_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """গ্রুপে জয়েন আছে কিনা ভেরিফাই করার ফাংশন"""
    try:
        member = context.bot.get_chat_member(chat_id=REQUIRED_GROUP_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """স্টার্টিং কমাণ্ড ও জয়েন ভেরিফিকেশন"""
    user = update.effective_user
    if not is_user_member(context, user.id):
        keyboard = [
            [InlineKeyboardButton("গ্রুপে জয়েন করুন", url=f"https://t.me/{REQUIRED_GROUP_ID.replace('@', '')}")],
            [InlineKeyboardButton("ভেরিফাই করুন", callback_data="verify_membership")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("বটটি ব্যবহার করতে আগে আমাদের অফিসিয়াল গ্রুপে জয়েন হতে হবে:", reply_markup=reply_markup)
        return

    await update.message.reply_text(
        f"স্বাগতম {user.first_name}!\n"
        "কাজের ধরণ নির্বাচন করুন: Facebook নাকি Mail?\n"
        "/balance: আপনার ব্যালেন্স দেখতে কাজ জমা দিন\n"
        "/withdraw: সর্বনিম্ন উইথড্র {MIN_WITHDRAWAL} টাকা"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'verify_membership':
        if is_user_member(context, query.from_user.id):
            await query.edit_message_text("আপনার সদস্যপদ সফলভাবে ভেরিফাই হয়েছে! এখন কাজ শুরু করতে পারেন। /start দিন")
        else:
            await query.edit_message_text("আপনি এখনও গ্রুপে জয়েন করেননি। অনুগ্রহ করে গ্রুপে জয়েন করেন আবার চেষ্টা করুন।")

async def check_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ব্যালেন্স চেক করার ফাংশন"""
    user_id = str(update.effective_user.id)
    
    # শিট থেকে তথ্য সংগ্রহ
    try:
        records = sheet.get_all_records()
        user_data = [r for r in records if str(r.get('User ID')) == user_id]
        
        approved_tasks = sum(1 for r in user_data if r.get('Status') == 'Approved')
        pending_tasks = sum(1 for r in user_data if r.get('Status') == 'Pending')
        
        total_balance = 0.0
        for r in user_data:
            if r.get('Status') == 'Approved':
                task_type = r.get('Task Type')
                if task_type == 'Facebook':
                    total_balance += RATE_FACEBOOK
                elif task_type == 'Gmail':
                    total_balance += RATE_GMAIL
                    
        await update.message.reply_text(
            f"👤 ইউজার: {update.effective_user.first_name}\n"
            f"✅ অনুমোদিত কাজ (Approved_tasks): {approved_tasks}\n"
            f"⏳ রিভিউ পেন্ডিং কাজ (Pending_tasks): {pending_tasks}\n"
            f"💰 বর্তমান মোট ব্যালেন্স: {total_balance} টাকা"
        )
    except Exception as e:
        await update.message.reply_text("তথ্য সংগ্রহ করতে সমস্যা হয়েছে। অনুগ্রহ করে পরে চেষ্টা করুন।")

async def submit_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """কাজের ডাটা জমা নেওয়া (Status: Pending)"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "N/A"
    task_type = "Facebook" # অথবা "Gmail"
    proof = update.message.text

    sheet.append_row([user_id, username, task_type, proof, "Pending"])
    await update.message.reply_text("আপনার কাজটি জমা নেওয়া হয়েছে এবং এটি 'Review Pending' হিসেবে রয়েছে।")

async def withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """উইথড্র অপশন"""
    user_id = str(update.effective_user.id)
    
    records = sheet.get_all_records()
    user_data = [r for r in records if str(r.get('User ID')) == user_id]
    
    total_balance = 0.0
    for r in user_data:
        if r.get('Status') == 'Approved':
            if r.get('Task Type') == 'Facebook':
                total_balance += RATE_FACEBOOK
            elif r.get('Task Type') == 'Gmail':
                total_balance += RATE_GMAIL

    if total_balance >= MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"আপনার পর্যাপ্ত ব্যালেন্স রয়েছে ({total_balance} টাকা)!\n"
            "উইথড্র নেওয়ার জন্য আপনার বিকাশ নম্বর লিখে পাঠান।"
        )
    else:
        await update.message.reply_text(
            f"আপনার ব্যালেন্স ({total_balance} টাকা)।\n"
            f"উইথড্র করতে অন্তত ({MIN_WITHDRAWAL}) টাকা প্রয়োজন।"
        )

# ৪. বট শু করার প্রধান অংশ (Main Execution)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("balance", check_balance))
    app.add_handler(CommandHandler("withdraw", withdraw))
    app.add_handler(CallbackQueryHandler(button_handler))

    # কাজের প্রুফ জমা নেওয়ার হ্যান্ডলার
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, submit_task))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
    
