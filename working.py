#Подключаем все необходимые библиотеки
import telebot
from telebot import types
import json
import os
import time
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from telebot import TeleBot

#Вводим наш токен
API_TOKEN = '7945887994:AAHXuomYahEN6oafMnEH7jganZ9lqRIR2dI'
bot = telebot.TeleBot(API_TOKEN)

# Создаем экземпляр планировщика
scheduler = BackgroundScheduler()

#Создаем файл, где хранится информация о наполнении холодильника
DATA_FILE = 'data.json'

# Хранение ID сообщений
message_ids = []

#Функция открытия и чтения файла
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    return []

#Функция добавления записей в файл
def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, ensure_ascii=False)

data_list = load_data()

#Функция, управляющая порядковым номером в списке
def update_ids():
    for index, item in enumerate(data_list):
        item['id'] = index + 1

# Обработчик команды /start
@bot.message_handler(commands=['start']) 
def send_welcome(message):
    text = 'Привет! Я - твой помощник, буду сообщать тебе о наполнении твоего холодильника и сроках годности продуктов в нем.\nСпасибо что выбрал меня!\nНе знаешь что делать? Напиши "/help"'
    bot.reply_to(message, text)

# Обработчик команды /help
@bot.message_handler(commands=['help'])
def send_help(message):
    text = 'Чтобы начать работу, тебе нужно ввести команду "/menu".\nОна покажет тебе перечень доступных действий.'
    bot.reply_to(message, text)
    
# Функция, выводящая список доступных команд с выбором через кнопку йибать!
@bot.message_handler(commands=['menu'])
def send_menu(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    button1 = KeyboardButton("Показать список")
    button2 = KeyboardButton("Добавить продукт")
    button3 = KeyboardButton("Удалить продукт")
    button4 = KeyboardButton("Скоро истекает срок годности")
    button5 = KeyboardButton("Выйти")
    markup.add(button1, button2, button3, button4, button5)

    bot.send_message(message.chat.id, "Вот что ты можешь сделать:\n1.Вывести список продуктов.\n2.Добавить продукт в список.\n3.Удалить продукт из списка.\n4.Просмотреть продукты с истекающим сроком годности.\n5.Выйти", reply_markup=markup)
    
#Кнопошка внутри
@bot.message_handler(func=lambda message: True)
def handle_text(message):
    if message.text == "Показать список":
        view_list(message)
    elif message.text == "Добавить продукт":
        add_item(message)
    elif message.text == "Удалить продукт":
        remove_item(message)
    elif message.text == "Скоро истекает срок годности":
        show_deads(message)
    elif message.text == "Выйти":
        clear_chat(message)

#Команда, с помощью которой можно просмотреть список
@bot.message_handler(commands=['view'])
def view_list(message):
    if not data_list:
        bot.send_message(message.chat.id, "Список пуст.")
        return
    
    response = "Сейчас в холодильнике:\n"
    for item in data_list:
        if isinstance(item, dict) and all(k in item for k in ('id', 'name', 'expiry_date')):
            response += f"{item['id']}: {item['name']} (годен до {item['expiry_date']})\n"
        else:
            print("Неверный элемент:", item)  # Отладочный вывод для неверного элемента
    bot.send_message(message.chat.id, response)

#Функция добавления элемента в список
@bot.message_handler(commands=['add'])
def add_item(message):
    bot.send_message(message.chat.id, "Введите название продукта:")
    bot.register_next_step_handler(message, process_name)

#Функция добавления срока годности элементу списка
def process_name(message):
    name = message.text
    bot.send_message(message.chat.id, "Введите дату окончания срока годности (в формате DD.MM.YYYY):")
    bot.register_next_step_handler(message, process_date, name)

#Функция, которая объединяет действия двух предыдущих и проверяет на ошибки 
def process_date(message, name):
    expiry_date = message.text
    try:
        # Проверка на корректный формат даты
        expiry_date_obj = datetime.strptime(expiry_date, '%d.%m.%Y')
        # Получаем текущую дату без времени
        current_date = datetime.now().date()
        
        # Сравниваем даты
        if expiry_date_obj.date() < current_date:
            bot.send_message(message.chat.id, "Ты купил просрочку! Проверь дату еще раз.")
            bot.register_next_step_handler(message, process_date, name)  # Запрос даты снова
            return
        
        item_id = len(data_list) + 1  # Автоматически присваиваем ID
        data_list.append({'id': item_id, 'name': name, 'expiry_date': expiry_date})
        save_data(data_list)
        bot.send_message(message.chat.id, "Продукт добавлен в холодильник.")
    except ValueError:
        bot.send_message(message.chat.id, "Некорректный формат даты. Попробуйте еще раз.")
        bot.register_next_step_handler(message, process_date, name)

#Функция удаления элементов из списка
@bot.message_handler(commands=['remove'])
def remove_item(message):
    if not data_list:
        bot.send_message(message.chat.id, "В твоем холодильнике пусто...")
        return
    view_list(message)  # Используем функцию для просмотра списка
    bot.send_message(message.chat.id, "Введите номер продукта для удаления из списка:")
    bot.register_next_step_handler(message, process_remove)

#Функция описывающая работу предыдущей
def process_remove(message):
    try:
        item_id = int(message.text)
        global data_list
        data_list = [item for item in data_list if item['id'] != item_id]
        update_ids()  # Обновляем ID
        save_data(data_list)
        bot.send_message(message.chat.id, "Продукт удален из списка.")
    except ValueError:
        bot.send_message(message.chat.id, "Некорректный номер. Попробуйте еще раз.")
    
#Функция для удаления истории сообщений
@bot.message_handler(commands=['clear'])
def clear_chat(message):
    # Сохраним ID последнего сообщения, чтобы удалять его
    current_message = bot.send_message(message.chat.id, "Перед выходом надо убрать за собой! Удаляю чат...")    
    time.sleep(1)  # Пауза для получения ID отправленного сообщения
    message_ids.append(current_message.message_id)

    # Удаление всех сообщений в чате
    try:
        # Пример удаления последних 100 сообщений (или всех, если их меньше)
        for msg_id in range(current_message.message_id - 1, current_message.message_id - 101, -1):
            bot.delete_message(message.chat.id, msg_id)
            message_ids.append(msg_id)
            time.sleep(0.5)  # Задержка между удалениями для избежания ограничения API

    except Exception as e:
        print(f"Ошибка при удалении сообщений: {e}")

    # Уведомление о завершении удаления
    bot.send_message(message.chat.id, "Пока! Приходи еще!\nЧтобы снова запустить бота выполни команду '/start'\nЧтобы вывести перечень действий выполни команду '/menu'")
    
# Обработчик для команды или сообщения
@bot.message_handler(commands=['show_deads'])
def show_deads(message):
    check_and_notify_expiry(message)
    
#Ебейшая функция которая делает 2 дела 
def check_and_notify_expiry(message=None):
    current_date = datetime.now()
    expiring_items = []
    
    for item in data_list:
        if isinstance(item, dict) and all(k in item for k in ('id', 'name', 'expiry_date')):
            expiry_date = datetime.strptime(item['expiry_date'], '%d.%m.%Y')
            if 0 <= (expiry_date - current_date).days < 7:
                expiring_items.append(item)
    
    if expiring_items:
        response = "Срок годности продуктов, истекающий менее чем через 7 дней:\n"
        for item in expiring_items:
            response += f"{item['id']}: {item['name']} (годен до {item['expiry_date']})\n"
    else:
        response = "Нет продуктов, срок годности которых истекает менее чем через 7 дней."

    # Отправляем сообщение в чат, если message передан
    if message:
        bot.send_message(message.chat.id, response)
    else:
        # Если message не передан, используем заранее заданный chat_id
        chat_id = '682054183'
        bot.send_message(chat_id, response)

# Запускаем планировщик с CronTrigger для ежедневного выполнения в 6:00
scheduler.add_job(check_and_notify_expiry, trigger=CronTrigger(hour=6, minute=40))
scheduler.start()


bot.polling(none_stop=True)
