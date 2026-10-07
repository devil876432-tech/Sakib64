import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# ---------------------------------------------------------
# ১. গুগল শিট কানেকশন সেটআপ (Google Sheets Integration)
# ---------------------------------------------------------
# আপনার সার্ভিস অ্যাকাউন্ট ইমেইল: facebook-bot@facebook-bot-510906.iam.gserviceaccount.com
# আপনার ডাউনলোড করা JSON ফাইলটির নাম বা পাথ নিচে 'service_account.json' এর জায়গায় দিন।

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
JSON_FILE_PATH = "service_account.json"  # আপনার ডাউনলোড করা JSON ফাইলের নাম

try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE_PATH, SCOPE)
    client = gspread.authorize(creds)
    # আপনার গুগল শিটের সঠিক নামটি নিচে লিখুন
    sheet = client.open("Facebook k Sheet").sheet1 
except Exception as e:
    print(f"Google Sheets Connection Error: {e}")

# ---------------------------------------------------------
# ২. বটের কনফিগারেশন ও প্রাইসিং (Bot Configuration)
# ---------------------------------------------------------
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # আপনার টেলিগ্রাম বট টোকেন দিন
REQUIRED_GROUP_ID = "@your_group_username"  # ভেরিফিকেশনের জন্য গ্রুপ/চ্যানেল ইউজারনেম

RATE_FACEBOOK = 4.0   # ফেসবুক কাজের রেট (৪ টাকা)
RATE_GMAIL = 15.0     # জিমেইল কাজের রেট (১৫ টাকা)
MIN_WITHDRAWAL = 300  # সর্বনিম্ন উইথড্রয়াল (৩০০ টাকা)

# ---------------------------------------------------------
# ৩. বট ফাংশনাল কোড (Bot Core Functions)
# ---------------------------------------------------------

def is_user_member(context: CallbackContext, user_id: int) -> bool:
    """গ্রুপে জয়েন আছে কিনা ভেরিফাই করার ফাংশন"""
    try:
        member = context.bot.get_chat_member(chat_id=REQUIRED_GROUP_ID, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    if not is_user_member(context, user.id):
        keyboard = [
            [InlineKeyboardButton("গ্রুপে জয়েন করুন", url=f"https://t.me/{REQUIRED_GROUP_ID.replace('@', '')}")],
            [InlineKeyboardButton("ভেরিফাই করুন", callback_data="verify_membership")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("বটটি ব্যবহার করতে আপনাকে অবশ্যই আমাদের অফিশিয়াল গ্রুপে জয়েন হতে হবে।", reply_markup=reply_markup)
        return

    update.message.reply_text(
        f"স্বাগতম {user.first_name}!\n\n"
        f"কাজ ও ব্যালেন্স দেখতে অপশন সিলেক্ট করুন:\n"
        f"• ফেসবুক কাজ: {RATE_FACEBOOK} টাকা\n"
        f"• জিমেইল কাজ: {RATE_GMAIL} টাকা\n"
        f"• সর্বনিম্ন উইথড্র: {MIN_WITHDRAWAL} টাকা (বিকাশ)\n\n"
        f"কমান্ডসমূহ:\n/balance - ব্যালেন্স ও কাজের সামারি দেখুন\n/withdraw - টাকা তোলার জন্য আবেদন করুন"
    )

def verify_button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    
    if is_user_member(context, user_id):
        query.edit_message_text("আপনার সদস্যপদ সফলভাবে ভেরিফাইড হয়েছে! এখন আপনি কাজ শুরু করতে পারেন। /start দিন।")
    else:
        query.edit_message_text("আপনি এখনো গ্রুপে জয়েন করেননি! অনুগ্রহ করে আগে গ্রুপে জয়েন করে আবার চেষ্টা করুন।")

def check_balance(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    
    # গুগল শিট থেকে ইউজারের ডেটা পড়া
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
                    
        update.message.reply_text(
            f"📊 **আপনার অ্যাকাউন্টের বিবরণ:**\n\n"
            f"✅ অনুমোদিত কাজ: {approved_tasks} টি\n"
            f"⏳ রিভিউ পেন্ডিং কাজ: {pending_tasks} টি\n"
            f"💰 বর্তমান মোট ব্যালেন্স: {total_balance} টাকা\n\n"
            f"(সর্বনিম্ন উইথড্রয়াল সীমা: {MIN_WITHDRAWAL} টাকা)"
        )
    except Exception as e:
        update.message.reply_text("ব্যালেন্স দেখতে সমস্যা হচ্ছে। পরে চেষ্টা করুন।")

def submit_task(update: Update, context: CallbackContext):
    user = update.effective_user
    task_type = "Facebook"  # অথবা "Gmail"
    proof = update.message.text
    
    # গুগল শিটে কাজ জমা রাখা (Status: Pending)
    try:
        sheet.append_row([str(user.id), user.username, task_type, proof, "Pending"])
        update.message.reply_text(
            "আপনার কাজটি জমা নেওয়া হয়েছে এবং এটি 'Review Pending' হিসেবে আছে। "
            "এডমিন রিভিউ করে অ্যাপ্রুভ করলে ব্যালেন্স যোগ হয়ে যাবে।"
        )
    except Exception as e:
        update.message.reply_text("কাজ জমা নিতে সমস্যা হয়েছে। আবার চেষ্টা করুন।")

def withdraw(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    
    # শিট থেকে ব্যালেন্স চেক
    try:
        records = sheet.get_all_records()
        user_data = [r for r in records if str(r.get('User ID')) == user_id and r.get('Status') == 'Approved']
        
        total_balance = 0.0
        for r in user_data:
            if r.get('Task Type') == 'Facebook':
                total_balance += RATE_FACEBOOK
            elif r.get('Task Type') == 'Gmail':
                total_balance += RATE_GMAIL

        if total_balance >= MIN_WITHDRAWAL:
            update.message.reply_text(
                f"আপনার পর্যাপ্ত ব্যালেন্স রয়েছে ({total_balance} টাকা)।\n"
                f"উইথড্র নেওয়ার জন্য আপনার বিকাশ নম্বরটি লিখে পাঠাল।"
            )
        else:
            update.message.reply_text(
                f"আপনার ব্যালেন্স {total_balance} টাকা। "
                f"উইথড্র করতে অন্তত {MIN_WITHDRAWAL} টাকা প্রয়োজন।"
            )
    except Exception as e:
        update.message.reply_text("উইথড্র রিকোয়েস্ট প্রসেস করতে সমস্যা হচ্ছে।")

# ---------------------------------------------------------
# ৪. বট শুরু করার প্রধান অংশ (Main Execution)
# ---------------------------------------------------------
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("balance", check_balance))
    dp.add_handler(CommandHandler("withdraw", withdraw))
    dp.add_handler(CallbackQueryHandler(verify_button, pattern="^verify_membership$"))
    
    # কাজের প্রুফ জমা নেওয়ার হ্যান্ডলার
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, submit_task))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
  
