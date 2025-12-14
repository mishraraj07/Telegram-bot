import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Replace with your bot token and username
BOT_TOKEN = '8454350428:AAExCcNWl9V9xQ36S5NRxPCDGnQ5q5HcGmw'
BOT_USERNAME = 'vilianinstaviral_bot'  # e.g., 'mybot'

# Required channels for verification (usernames without @)
REQUIRED_CHANNELS = ['@wsearn07', '@wspromot']  # Add your channels here

# Database setup
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

# Create tables
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    points INTEGER DEFAULT 0,
    referred_by INTEGER,
    withdrawal_index INTEGER DEFAULT 0
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, points INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT,
    type TEXT,  -- 'channel' or 'link'
    target TEXT,  -- channel username or link
    points INTEGER
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS completed_tasks (user_id INTEGER, task_id INTEGER, PRIMARY KEY(user_id, task_id))''')

# Add initial admin
cursor.execute('INSERT OR IGNORE INTO admins (id) VALUES (5750415767)')
conn.commit()

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id
    
    # Check if new user
    cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('INSERT INTO users (id) VALUES (?)', (user_id,))
        conn.commit()
        # Notify admins
        cursor.execute('SELECT id FROM admins')
        for admin_id in cursor.fetchall():
            await context.bot.send_message(chat_id=admin_id[0], text=f'New user joined: {user_id}')
    
    # Check referral
    if context.args and context.args[0].startswith('ref_'):
        referrer_id = int(context.args[0][4:])
        cursor.execute('UPDATE users SET referred_by = ? WHERE id = ?', (referrer_id, user_id))
        cursor.execute('UPDATE users SET points = points + 10 WHERE id = ?', (referrer_id,))
        conn.commit()
        await context.bot.send_message(chat_id=referrer_id, text='You earned 10 points for a referral!')
    
    # Welcome message with verify button
    keyboard = [[InlineKeyboardButton("Verify", callback_data='verify')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome to this bot! Join channels to use this bot.', reply_markup=reply_markup)

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    # Check membership
    all_joined = True
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=f'@{channel}', user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                all_joined = False
                break
        except:
            all_joined = False
            break
    
    if all_joined:
        await query.edit_message_text('Access granted! Refer this bot to earn 10 points per person. Use /refer for your link. Use /withdrawal to withdraw.')
    else:
        await query.edit_message_text('Please join the required channels first.')

async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    link = f't.me/{BOT_USERNAME}?start=ref_{user_id}'
    await update.message.reply_text(f'Your referral link: {link}')

async def withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    cursor.execute('SELECT points, withdrawal_index FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    if user_data and user_data[0] >= 20:
        cursor.execute('SELECT file_id FROM videos')
        videos = cursor.fetchall()
        if videos:
            index = user_data[1] % len(videos)
            file_id = videos[index][0]
            cursor.execute('UPDATE users SET points = points - 20, withdrawal_index = withdrawal_index + 1 WHERE id = ?', (user_id,))
            conn.commit()
            await update.message.reply_document(document=file_id, caption='Here is your withdrawal video!')
        else:
            await update.message.reply_text('No videos available for withdrawal.')
    else:
        await update.message.reply_text('Insufficient points. Need 20 points.')

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    cursor.execute('SELECT id FROM admins WHERE id = ?', (user_id,))
    if cursor.fetchone():
        keyboard = [
            [InlineKeyboardButton("Add Admin", callback_data='add_admin')],
            [InlineKeyboardButton("Broadcast", callback_data='broadcast')],
            [InlineKeyboardButton("Upload Video", callback_data='upload_video')],
            [InlineKeyboardButton("Set Withdrawal", callback_data='set_withdrawal')],
            [InlineKeyboardButton("Create Code", callback_data='create_code')],
            [InlineKeyboardButton("Create Task", callback_data='create_task')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Admin Panel:', reply_markup=reply_markup)
    else:
        await update.message.reply_text('Access denied.')

# Handlers for admin actions (simplified; expand as needed)
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    
    if data == 'add_admin':
        await query.edit_message_text('Send the new admin ID.')
        context.user_data['action'] = 'add_admin'
    elif data == 'broadcast':
        await query.edit_message_text('Send the message to broadcast.')
        context.user_data['action'] = 'broadcast'
    elif data == 'upload_video':
        await query.edit_message_text('Send the video file.')
        context.user_data['action'] = 'upload_video'
    elif data == 'set_withdrawal':
        await query.edit_message_text('Send the video or link for withdrawal.')
        context.user_data['action'] = 'set_withdrawal'
    elif data == 'create_code':
        await query.edit_message_text('Send code and points (e.g., code 50).')
        context.user_data['action'] = 'create_code'
    elif data == 'create_task':
        await query.edit_message_text('Send task: description, type (channel/link), target, points (e.g., Join @channel, channel, @channel, 10).')
        context.user_data['action'] = 'create_task'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    action = context.user_data.get('action')
    
    if action == 'add_admin':
        try:
            new_admin_id = int(update.message.text)
            cursor.execute('INSERT INTO admins (id) VALUES (?)', (new_admin_id,))
            conn.commit()
            await update.message.reply_text('Admin added.')
        except:
            await update.message.reply_text('Invalid ID.')
    elif action == 'broadcast':
        cursor.execute('SELECT id FROM users')
        for user in cursor.fetchall():
            await context.bot.send_message(chat_id=user[0], text=update.message.text)
        await update.message.reply_text('Broadcast sent.')
    elif action == 'upload_video':
        if update.message.document:
            file_id = update.message.document.file_id
            cursor.execute('INSERT INTO videos (file_id) VALUES (?)', (file_id,))
            conn.commit()
            await update.message.reply_text('Video uploaded.')
    elif action == 'set_withdrawal':
        # Similar to upload_video; handle links if needed
        pass
    elif action == 'create_code':
        parts = update.message.text.split()
        if len(parts) == 2:
            code, points = parts[0], int(parts[1])
            cursor.execute('INSERT INTO codes (code, points) VALUES (?, ?)', (code, points))
            conn.commit()
            await update.message.reply_text('Code created.')
    elif action == 'create_task':
        parts = update.message.text.split(', ')
        if len(parts) == 4:
            desc, typ, target, pts = parts
            cursor.execute('INSERT INTO tasks (description, type, target, points) VALUES (?, ?, ?, ?)', (desc, typ, target, int(pts)))
            conn.commit()
            await update.message.reply_text('Task created.')
    
    context.user_data.pop('action', None)

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if context.args:
        code = context.args[0]
        cursor.execute('SELECT points FROM codes WHERE code = ?', (code,))
        result = cursor.fetchone()
        if result:
            cursor.execute('UPDATE users SET points = points + ? WHERE id = ?', (result[0], user_id))
            cursor.execute('DELETE FROM codes WHERE code = ?', (code,))
            conn.commit()
            await update.message.reply_text(f'Redeemed {result[0]} points!')
        else:
            await update.message.reply_text('Invalid code.')

async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cursor.execute('SELECT id, description FROM tasks')
    task_list = cursor.fetchall()
    if task_list:
        text = '\n'.join([f'{t[0]}: {t[1]}' for t in task_list])
        await update.message.reply_text(f'Tasks:\n{text}\nUse /complete <task_id> to complete.')
    else:
        await update.message.reply_text('No tasks available.')

async def complete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if context.args:
        task_id = int(context.args[0])
        cursor.execute('SELECT type, target, points FROM tasks WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        if task:
            # Check if already completed
            cursor.execute('SELECT 1 FROM completed_tasks WHERE user_id = ? AND task_id = ?', (user_id, task_id))
            if not cursor.fetchone():
                if task[0] == 'channel':
                    # Verify membership
                    try:
                        member = await context.bot.get_chat_member(chat_id=f'@{task[1]}', user_id=user_id)
                        if member.status in ['member', 'administrator', 'creator']:
                            cursor.execute('UPDATE users SET points = points + ? WHERE id = ?', (task[2], user_id))
                            cursor.execute('INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)', (user_id, task_id))
                            conn.commit()
                            await update.message.reply_text(f'Task completed! Earned {task[2]} points.')
                        else:
                            await update.message.reply_text('You are not a member of the channel.')
                    except:
                        await update.message.reply_text('Error verifying.')
                elif task[0] == 'link':
                    # For links, just award (not verifiable)
                    cursor.execute('UPDATE users SET points = points + ? WHERE id = ?', (task[2], user_id))
                    cursor.execute('INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)', (user_id, task_id))
                    conn.commit()
                    await update.message.reply_text(f'Task completed! Earned {task[2]} points.')
            else:
                await update.message.reply_text('Task already completed.')

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("refer", refer))
    application.add_handler(CommandHandler("withdrawal", withdrawal))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CommandHandler("tasks", tasks))
    application.add_handler(CommandHandler("complete", complete))
    application.add_handler(CallbackQueryHandler(verify, pattern='^verify$'))
    application.add_handler(CallbackQueryHandler(handle_admin_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == '__main__':
    main()
