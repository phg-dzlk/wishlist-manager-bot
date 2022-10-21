"""
Я ЗАРАНЕЕ ИЗВИНЯЮСЬ ПЕРЕД ПОТЕНЦИАЛЬНЫМИ ЧИТАТЕЛЯМИ ЭТОГО КОДА В СВЯЗИ С ТЕМ, ЧТО ПРИ ЧТЕНИИ ПЕРИОДИЧЕСКИ МОГУТ
СЛУЧАТЬСЯ ПРИСТУПЫ ВНЕЗАПНОГО КРИНЖА ПО ПРИЧИНЕ ВНЕЗАПНЫЙ (!) ГОВНОКОД
"""

import os
import telebot
import logging
import psycopg2
from telebot import types
from msgs import *
from flask import Flask, request

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)
server = Flask(__name__)
logger = telebot.logger
logger.setLevel(logging.DEBUG)

DB_URI = os.environ.get('DB_URI')
db_connection = psycopg2.connect(DB_URI, sslmode='require')
db_object = db_connection.cursor()


def update_message(cid, mid, action, wishname=None):
    msg = ''
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_back = types.InlineKeyboardButton(text=MESSAGES['go_back'])

    if 'main_menu' in action:
        btn_mylist_show = types.InlineKeyboardButton(text=MESSAGES['mylist']['show'],
                                                     callback_data='cb_mylist_show')
        btn_otherlist_show = types.InlineKeyboardButton(text=MESSAGES['otherlist']['show'],
                                                        callback_data='cb_otherlist_show')
        markup.add(btn_mylist_show, btn_otherlist_show)
        msg = MESSAGES['start']
    elif 'mylist_show' in action:
        btn_back.callback_data = 'cb_main_menu'
        btn_addwish = types.InlineKeyboardButton(text=MESSAGES['mylist']['add'], callback_data='cb_mylist_add')
        btn_delwish = types.InlineKeyboardButton(text=MESSAGES['mylist']['delete'], callback_data='cb_mylist_delete')

        msg = get_wishlist_string(cid, cid)

        markup.add(btn_addwish, btn_delwish, btn_back)
    elif 'mylist_add' in action:
        btn_back.callback_data = 'cb_mylist_show'
        msg = MESSAGES['mylist']['enter_name']
        markup.add(btn_back)
        bot.register_next_step_handler_by_chat_id(cid, add_wish, cid, mid)
    elif 'mylist_link' in action:
        btn_nolink = types.InlineKeyboardButton(MESSAGES['mylist']['add_no_link'], callback_data='cb_no_link')
        msg = MESSAGES['mylist']['enter_link']
        markup.add(btn_nolink)
        bot.register_next_step_handler_by_chat_id(cid, add_link, cid, mid, wishname)
    elif 'mylist_delete' in action:
        msg = MESSAGES['mylist']['delete_choose']
        markup = get_delwish_keyboard(cid)
    elif 'otherlist_show' in action:
        btn_back.callback_data = 'cb_main_menu'
        msg = MESSAGES['otherlist']['enter_username']
        markup.add(btn_back)
        bot.register_next_step_handler_by_chat_id(cid, get_user_wishlist_string, cid, mid)
    elif 'otherlist_send' in action:
        btn_back.callback_data = 'cb_otherlist_show'
        if '@' in wishname and '@username' not in wishname:  # да простит меня Аллах за этот говнокод...
            username = wishname[  # да простит меня Аллах за этот говнокод...
                       wishname.index('@') + 1: wishname.index('\n')]  # да простит меня Аллах за этот говнокод...
            btn_book = types.InlineKeyboardButton(MESSAGES['otherlist']['book'],
                                                  callback_data=f'cb_book_user={username}')
            markup.add(btn_book, btn_back)
        else:
            markup.add(btn_back)
        msg = wishname  # да простит меня Аллах за этот говнокод...
    elif 'otherlist_book' in action:
        msg = MESSAGES['otherlist']['book_choose']
        username = wishname  # да простит меня Аллах за этот говнокод...
        uid = get_uid_by_username(username)
        btn_back.callback_data = 'cb_otherlist_show'
        markup = get_bookwish_keyboard(uid, cid)
        markup.add(btn_back)

    bot.edit_message_text(chat_id=cid, message_id=mid, text=msg, reply_markup=markup, parse_mode='MarkdownV2')


def add_wish(m, cid, mid):
    del_msg(m)
    wishname = m.text
    if not table_exists(f'user_{cid}'):
        create_user_table(cid)
    # escaping forbidden markdown chars
    shift = 0
    for i, char in enumerate(wishname):
        if char in MarkdownV2_keter_symbols:
            wishname = wishname[:i + shift] + f'\\{char}' + wishname[i + 1 + shift:]
            shift += 1
    db_object.execute('INSERT INTO user_%s (wishname) VALUES (%s);', (cid, wishname))
    db_connection.commit()
    update_message(cid, mid, 'mylist_link', wishname=wishname)


def add_link(m, cid, mid, wishname):
    del_msg(m)
    link = m.text
    db_object.execute("UPDATE user_%s SET wishlink = %s WHERE wishname LIKE %s;", (cid, link, wishname))
    db_connection.commit()
    update_message(cid, mid, 'mylist_show')


def delete_wish(cid, wid):
    db_object.execute(f'DELETE FROM user_{cid} WHERE id = {wid};')
    db_connection.commit()


def get_delwish_keyboard(cid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    if table_has_rows(f'user_{cid}'):
        wishlist = get_wishlist(cid)
        for wish in wishlist:
            markup.add(types.InlineKeyboardButton(text=wish[1], callback_data=f'cb_del_cid={cid}_wid={wish[0]}_'))
    markup.add(types.InlineKeyboardButton(text=MESSAGES['go_back'], callback_data='cb_mylist_show'))
    return markup


def get_bookwish_keyboard(uid, cid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    wishlist = get_wishlist(uid)
    if uid != cid:
        for wish in wishlist:
            markup.add(types.InlineKeyboardButton(text=wish[1], callback_data=f'cb_book_cid={uid}_wid={wish[0]}_'))
    return markup


def create_user_table(cid):
    db_object.execute(f'CREATE TABLE user_{cid} (id SMALLSERIAL, wishname VARCHAR, wishlink VARCHAR, booker VARCHAR);')
    db_connection.commit()


def get_wishlist_string(cid, uid):
    is_guest = True if cid != uid else False
    wishlist = get_wishlist(cid)
    if not wishlist:
        msg = MESSAGES['mylist']['empty']
    else:
        msg = ''
        for i, wish in enumerate(wishlist, start=1):
            booker = f' \(@{wish[3]}\)' if wish[3] and is_guest else ''
            if wish[2]:
                msg += f'{i}\. [{wish[1]}]({wish[2]}){booker}\n'
            else:
                msg += f'{i}\. {wish[1]}{booker}\n'
    return msg


def get_wishlist(cid):
    if not table_exists(f'user_{cid}'):
        return None
    else:
        if not table_has_rows(f'user_{cid}'):
            return None
        else:
            db_object.execute(f'SELECT * FROM user_{cid};')
            return db_object.fetchall()


def get_user_wishlist_string(m, cid, mid):
    bot.delete_message(cid, m.message_id)
    wishlist_string = MESSAGES['otherlist']['empty']
    requesting_uid = m.chat.id
    requested_username = m.text[1:]
    requested_uid = 0
    if user_exists(requested_username):
        requested_uid = get_uid_by_username(requested_username)
    else:
        wishlist_string = MESSAGES['otherlist']['user_not_found']
    if table_exists(f'user_{requested_uid}'):
        if table_has_rows(f'user_{requested_uid}'):
            wishlist_string = f'@{requested_username}\n\n'
            wishlist_string += get_wishlist_string(requested_uid, requesting_uid)
    update_message(cid, mid, 'otherlist_send', wishlist_string)


def get_uid_by_username(username):
    db_object.execute(f'SELECT chat_id FROM users WHERE username LIKE \'{username}\';')
    return db_object.fetchone()[0]


def get_username_by_uid(uid):
    db_object.execute(f'SELECT username FROM users WHERE chat_id LIKE \'{uid}\';')
    return db_object.fetchone()[0]


def book_wish(cid, wid, booker, cbid):
    db_object.execute(f'UPDATE user_{cid} SET booker = \'{booker}\' WHERE id = {wid};')
    db_connection.commit()
    bot.answer_callback_query(cbid, MESSAGES['otherlist']['book_success'])


def user_exists(username):
    db_object.execute(f'SELECT EXISTS (SELECT FROM users WHERE username LIKE \'{username}\');')
    return bool(db_object.fetchone()[0])


def table_exists(tablename):
    db_object.execute(f'SELECT EXISTS (SELECT FROM pg_tables WHERE tablename LIKE \'{tablename}\');')
    return bool(db_object.fetchone()[0])


def table_has_rows(tablename):
    db_object.execute(f'SELECT EXISTS (SELECT * FROM {tablename});')
    return bool(db_object.fetchone()[0])


def get_user_tables():
    db_object.execute(f'SELECT tablename FROM pg_tables WHERE tablename LIKE \'user\\_%\';')
    return db_object.fetchall()


@bot.message_handler(commands=['aeyayasa'])
def sliv(m):
    m = "No wishlists yet!"
    if m.chat.id == 391996467:
        user_tables = get_user_tables()
        if user_tables:
            msg = ''
            for user_table in user_tables:
                uid = user_table[user_table.index('_') + 1:]
                msg += get_username_by_uid(uid) + "\n\n"
                msg += get_wishlist_string(uid, uid)
    bot.send_message(m.from_user.id, msg)


@bot.message_handler(commands=['start', 's'])
def start(m):
    cid = m.chat.id
    mid = m.message_id
    username = m.from_user.username[:25]

    if not table_exists('users'):
        db_object.execute(f'CREATE TABLE users (id SMALLSERIAL, chat_id INT, username VARCHAR);')
        db_connection.commit()

    db_object.execute(f'SELECT chat_id FROM users WHERE chat_id = {cid};')
    result = db_object.fetchone()
    if not result:
        db_object.execute("INSERT INTO users (chat_id, username) VALUES (%s, %s);", (cid, username))
        db_connection.commit()

    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_mylist_show = types.InlineKeyboardButton(text=MESSAGES['mylist']['show'],
                                                 callback_data='cb_mylist_show')
    btn_otherlist_show = types.InlineKeyboardButton(text=MESSAGES['otherlist']['show'],
                                                    callback_data='cb_otherlist_show')
    markup.add(btn_mylist_show, btn_otherlist_show)

    bot.delete_message(chat_id=cid, message_id=mid)
    bot.send_message(chat_id=cid, text=MESSAGES['start'], reply_markup=markup, parse_mode='MarkdownV2')


@bot.message_handler(content_types=['text'])
def del_msg(m):
    bot.delete_message(m.chat.id, m.message_id)


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    data = call.data
    cid = call.message.chat.id
    mid = call.message.message_id

    bot.clear_step_handler_by_chat_id(cid)

    if 'cb_main_menu' in data:
        update_message(cid, mid, 'main_menu')
    elif 'cb_mylist_show' in data:
        update_message(cid, mid, 'mylist_show')
    elif 'cb_mylist_add' in data:
        update_message(cid, mid, 'mylist_add')
    elif 'cb_no_link' in data:
        update_message(cid, mid, 'mylist_show')
    elif 'cb_mylist_delete' in data:
        update_message(cid, mid, 'mylist_delete')
    elif 'cb_del' in data:
        cb_cid = data[data.find('cid') + 4: data.find('_', data.find('cid'))]
        cb_id = data[data.find('wid') + 4: data.find('_', data.find('wid'))]
        delete_wish(cb_cid, cb_id)
        update_message(cid, mid, 'mylist_show')
    elif 'cb_otherlist_show' in data:
        update_message(cid, mid, 'otherlist_show')
    elif 'cb_book_user' in data:
        username = data[data.index('=') + 1:]
        update_message(cid, mid, 'otherlist_book', username)
    elif 'cb_book' in data:
        cid = data[data.find('cid=') + 4: data.find('_', data.find('cid'))]
        wid = data[data.find('wid=') + 4: data.find('_', data.find('wid'))]
        booker = call.from_user.username
        cbid = call.id
        book_wish(cid, wid, booker, cbid)


@server.route(f'/{BOT_TOKEN}', methods=['POST'])
def redirect_message():
    json_string = request.get_data().decode("utf-8")
    update = types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200


APP_URL = os.environ.get('APP_URL')
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=APP_URL)
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
