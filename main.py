import asyncio
import json
import re
import random
from datetime import datetime
from telethon import TelegramClient, events

# ==========================
# CONFIG
# ==========================
api_id = 39165227
api_hash = "8e921bfc20e1fd176106bbbec1eabbe3"
session_name = "userbot"

GROUP_ID = -1003882301073
target_bot = "@centermarlindo_bot"
PIN = "4517"

# ==========================
# INIT
# ==========================
client = TelegramClient(session_name, api_id, api_hash)

transaction_queue = []
blocked_accounts = set()
daily_transactions = []

is_paused = False
is_processing = False
process_delay = (60, 120)  # delay antar transaksi
ME_ID = None  # akan diisi setelah client.start()

# ==========================
# LOAD & SAVE
# ==========================
def load_json(filename, default):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f)

blocked_accounts = set(load_json("blocked.json", []))
daily_transactions = load_json("daily_transactions.json", [])

def cleanup_old_transactions():
    today_str = datetime.now().strftime("%Y-%m-%d")
    global daily_transactions
    daily_transactions = [trx for trx in daily_transactions if trx["date"] == today_str]
    save_json("daily_transactions.json", daily_transactions)

cleanup_old_transactions()

# ==========================
# PARSE MESSAGE
# ==========================
def parse_message(text):
    text = text.upper()
    ewallet = None
    for w in ["DANA", "OVO", "GOPAY", "SHOPEEPAY"]:
        if w in text:
            ewallet = w
            break
    if not ewallet:
        return None

    rek_match = re.search(fr'{ewallet}[:\s]*([0-9]+)', text)
    nominal_match = re.search(r'BALANCE[:\s]*([\d,]+)', text)
    if not rek_match or not nominal_match:
        return None

    rek = rek_match.group(1)
    nominal = nominal_match.group(1).replace(",", "").replace(" ", "")
    return ewallet, rek, nominal

# ==========================
# PROCESS TRANSACTION
# ==========================
async def process_transaction(event):
    data = parse_message(event.raw_text)
    if not data:
        return

    ewallet, rek, nominal = data
    today_str = datetime.now().strftime("%Y-%m-%d")

    if rek in blocked_accounts:
        await event.reply(f"🚫 blocked (rekening: {rek})", reply_to=event.id)
        return

    for trx in daily_transactions:
        if trx["rek"] == rek and trx["nominal"] == nominal:
            await event.reply("🔄 duplicate (already processed)", reply_to=event.id)
            return

    formatted = f"{ewallet}B.{rek}.{nominal}.{PIN}"
    await client.send_message(target_bot, formatted)

    daily_transactions.append({
        "rek": rek,
        "nominal": nominal,
        "date": today_str,
        "msg_id": event.id
    })
    save_json("daily_transactions.json", daily_transactions)

# ==========================
# PROCESS QUEUE
# ==========================
async def process_queue():
    global is_processing
    if is_processing:
        return
    is_processing = True
    while True:
        if not is_paused and transaction_queue:
            event = transaction_queue.pop(0)
            try:
                await process_transaction(event)
            except Exception as e:
                print("ERROR:", e)
            await asyncio.sleep(random.randint(*process_delay))
        else:
            await asyncio.sleep(2)
    is_processing = False

# ==========================
# LISTENER GRUP
# ==========================
@client.on(events.NewMessage(chats=GROUP_ID))
async def handler(event):
    transaction_queue.append(event.message)

# ==========================
# UTILITY
# ==========================
def pm_or_saved(event):
    return event.is_private or (ME_ID and event.chat_id == ME_ID)

# ==========================
# COMMANDS PRIVATE / Saved Messages
# ==========================
@client.on(events.NewMessage(pattern=r'^/block (\d+)$', incoming=True))
async def block_account(event):
    if not pm_or_saved(event):
        return
    rekening = event.pattern_match.group(1)
    blocked_accounts.add(rekening)
    save_json("blocked.json", list(blocked_accounts))
    await event.reply(f"✅ rekening {rekening} has been blocked")

@client.on(events.NewMessage(pattern=r'^/unblock (\d+)$', incoming=True))
async def unblock_account(event):
    if not pm_or_saved(event):
        return
    rekening = event.pattern_match.group(1)
    if rekening in blocked_accounts:
        blocked_accounts.remove(rekening)
        save_json("blocked.json", list(blocked_accounts))
        await event.reply(f"✅ rekening {rekening} has been unblocked")
    else:
        await event.reply(f"⚠️ rekening {rekening} tidak ada di blocked list")

@client.on(events.NewMessage(pattern=r'^/paused$', incoming=True))
async def paused_system(event):
    if not pm_or_saved(event):
        return
    global is_paused
    is_paused = True
    await event.reply("⏸ proses forward transaksi dihentikan sementara")

@client.on(events.NewMessage(pattern=r'^/resume$', incoming=True))
async def resume_system(event):
    if not pm_or_saved(event):
        return
    global is_paused
    is_paused = False
    await event.reply("▶️ proses forward transaksi dilanjutkan")

# ==========================
# START
# ==========================
client.start()
print("Userbot running...")

# ambil ME_ID sekali saja
async def init_me():
    global ME_ID
    me = await client.get_me()
    ME_ID = me.id

loop = asyncio.get_event_loop()
loop.run_until_complete(init_me())
loop.create_task(process_queue())
loop.run_forever()
