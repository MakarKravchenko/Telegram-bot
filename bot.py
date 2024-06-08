import telebot
from telebot import types
import random
import psycopg2
import logging
import re

# Настройка логгирования
logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Настройка подключения к базе данных
conn = psycopg2.connect(dbname='bot3', user='bot', password='bot', host='localhost')
cursor = conn.cursor()

TOKEN = '6633378366:AAE_283zYVO-NkG1TNERpYK_WmWN95zSG70'
bot = telebot.TeleBot(TOKEN)

user_data = {}
asked_questions = {}

TEACHER_CHAT_ID = '848070869'
student_answers = {}

def initialize_user(chat_id):
    try:
        cursor.execute("SELECT user_id FROM users WHERE chat_id = %s", (chat_id,))
        result = cursor.fetchone()
        if result is None:
            markup = types.ForceReply(selective=False)
            msg = bot.send_message(chat_id, "Введите ваше имя, фамилию и email через запятую. Пример: 'Иванов, Иван, vanya@mail.ru'.", reply_markup=markup)
            bot.register_next_step_handler(msg, process_user_info)
        else:
            user_data[chat_id] = {'current_level': None, 'current_test': None, 'current_question': 0, 'correct_count': 0}
            send_level_selection(chat_id)
        logging.info(f"User initialized with chat_id: {chat_id}")
    except Exception as e:
        logging.error(f"Error initializing user {chat_id}: {e}")

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    initialize_user(chat_id)


def process_user_info(message):
    chat_id = message.chat.id
    try:
        parts = message.text.split(',')
        if len(parts) != 3:
            raise ValueError("Неправильный формат. Нужно ввести имя, фамилию и email, разделенные запятой. Пример: 'Иванов, Иван, vanya@mail.ru'.")

        name, surname, email = map(str.strip, parts)

        if not all(x.isalpha() for x in name.replace(" ", "")):
            raise ValueError("Имя должно содержать только буквы.")

        if not all(x.isalpha() for x in surname.replace(" ", "")):
            raise ValueError("Фамилия должна содержать только буквы.")

        if not is_valid_email(email):
            raise ValueError("Неверный формат электронной почты.")

        cursor.execute(
            "INSERT INTO users (chat_id, first_name, last_name, email, current_level, current_test, current_question, correct_count) VALUES (%s, %s, %s, %s, NULL, NULL, 0, 0)",
            (chat_id, name, surname, email)
        )
        conn.commit()
        user_data[chat_id] = {'current_level': None, 'current_test': None, 'current_question': 0, 'correct_count': 0,
                              'name': name, 'surname': surname, 'email': email}
        send_level_selection(chat_id)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка ввода: {e}")
        logging.error(f"Error processing user info for chat_id {chat_id}: {e}")
        initialize_user(chat_id)

def is_valid_email(email):
    
    return re.match(r"[a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+", email)

def load_user_state(chat_id):
    try:
        cursor.execute("SELECT current_level, current_test, current_question, correct_count FROM users WHERE chat_id = %s", (chat_id,))
        result = cursor.fetchone()
        if result:
            user_data[chat_id] = {
                "current_level": result[0],
                "current_test": result[1],
                "current_question": result[2],
                "correct_count": result[3]
            }
            logging.info(f"Loaded user state for chat_id {chat_id}: {user_data[chat_id]}")
        else:
            initialize_user(chat_id)
            logging.info(f"No user found, initialized new user for chat_id: {chat_id}")
    except psycopg2.Error as e:
        logging.error(f"Database error while loading user state for chat_id {chat_id}: {e}")

def reset_user_state(chat_id):
    user_data[chat_id] = {'current_level': user_data[chat_id]['current_level'], 'current_test': None, 'current_question': 0, 'correct_count': 0}
    student_answers[chat_id] = []  # Обнуляем список ответов при сбросе состояния
    update_user_state(chat_id)
    logging.info(f"State reset for user {chat_id}")

def update_user_state(chat_id, level=None, test=None, question=None, correct_count=None):
    user = user_data[chat_id]
    cursor.execute("UPDATE users SET current_level = %s, current_test = %s, current_question = %s, correct_count = %s WHERE chat_id = %s",
                   (level if level is not None else user['current_level'],
                    test if test is not None else user['current_test'],
                    question if question is not None else user['current_question'],
                    correct_count if correct_count is not None else user['correct_count'],
                    chat_id))
    conn.commit()
    logging.info(f"User state updated for chat_id {chat_id}: {user_data[chat_id]}")
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    initialize_user(chat_id)
    reset_user_state(chat_id)  # Reset state whenever /start or /help is invoked
    send_level_selection(chat_id)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    selection = call.data

    if selection in ['Школьник', 'Студент']:
        reset_user_state(chat_id)
        update_user_state(chat_id, level=selection)
        send_test_selection(chat_id)
    else:
        update_user_state(chat_id, test=selection)
        send_question(chat_id)

    # Убираем клавиатуру после обработки выбора, редактируем только клавиатуру сообщения
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)



def send_level_selection(chat_id):
    markup = types.InlineKeyboardMarkup()
    for level in ['Школьник', 'Студент']:
        button = types.InlineKeyboardButton(text=level, callback_data=level)
        markup.add(button)
    bot.send_message(chat_id, "Привет, я бот, который поможет тебе потренироваться в решении задач на комплексные числа! Выбери уровень и начнем!", reply_markup=markup)
    logging.info(f"Sent level selection to chat_id {chat_id}")

def send_test_selection(chat_id):
    load_user_state(chat_id)
    level = user_data[chat_id]["current_level"]
    if level is None:
        bot.send_message(chat_id, "Произошла ошибка при выборе уровня.")
        logging.error(f"Error in selecting level for chat_id {chat_id}")
        return
    try:
        markup = types.InlineKeyboardMarkup()
        cursor.execute("SELECT DISTINCT test FROM questions WHERE level = %s", (level,))
        tests = cursor.fetchall()
        for test in tests:
            test_name = test[0]
            button = types.InlineKeyboardButton(text=test_name, callback_data=test_name)
            markup.add(button)
        bot.send_message(chat_id, f"Выберите тест для уровня '{level}':", reply_markup=markup)
        logging.info(f"Sent test selection for level {level} to chat_id {chat_id}")
    except psycopg2.Error as e:
        logging.error(f"Database error during test selection for chat_id {chat_id}: {e}")

def send_question(chat_id):
    load_user_state(chat_id)
    level = user_data[chat_id]["current_level"]
    test_name = user_data[chat_id]["current_test"]
    current_question_index = user_data[chat_id]["current_question"]

    if chat_id not in asked_questions or current_question_index == 0:
        cursor.execute(
            "SELECT question_id, question, options, correct_option FROM questions WHERE level = %s AND test = %s",
            [level, test_name])
        all_questions = cursor.fetchall()
        random.shuffle(all_questions)
        asked_questions[chat_id] = all_questions  # Сохраняем перемешанные вопросы

    if current_question_index < len(asked_questions[chat_id]):
        question_data = asked_questions[chat_id][current_question_index]
        question_text = question_data[1]
        options = question_data[2]
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        for option in options:
            markup.add(types.KeyboardButton(option))
        bot.send_message(chat_id, question_text, reply_markup=markup)
        logging.info(f"Sent question to chat_id {chat_id}: {question_text}")

        # Обновляем индекс текущего вопроса после отправки вопроса
        user_data[chat_id]["current_question"] += 1
        update_user_state(chat_id)
    else:
        # Все вопросы завершены, отправляем результаты
        send_results_to_teacher(chat_id)
        bot.send_message(chat_id, "Вопросы закончились. Вы можете начать новый тест.", reply_markup=types.ReplyKeyboardRemove())
        send_level_selection(chat_id)  # Предлагаем начать новый тест
        logging.info(f"Test completed for chat_id {chat_id}")
@bot.message_handler(func=lambda message: True)
def handle_answer(message):
    chat_id = message.chat.id
    user_answer = message.text.strip()
    load_user_state(chat_id)

    if user_answer == '/start' or user_answer == '/help':
        send_welcome(message)
        return

    current_question_index = user_data[chat_id]["current_question"] - 1  # Последний отправленный вопрос

    if current_question_index < 0 or not asked_questions.get(chat_id):
        bot.send_message(chat_id, "Пожалуйста, используйте предложенные кнопки для ответа.")
        return

    question_data = asked_questions[chat_id][current_question_index]
    correct_answer = question_data[2][question_data[3]]  # Правильный ответ из опций
    options = question_data[2]  # Все возможные варианты ответа

    if user_answer not in options:
        bot.send_message(chat_id, "Пожалуйста, используйте предложенные кнопки для ответа.")
        return

    student_answers[chat_id].append({
        'question': question_data[1],
        'user_answer': user_answer,
        'correct_answer': correct_answer,
        'is_correct': user_answer == correct_answer
    })

    # Записываем ответ в базу данных
    save_user_answer(chat_id, question_data, user_answer)

    if user_answer == correct_answer:
        user_data[chat_id]["correct_count"] += 1

    update_user_state(chat_id)

    if user_data[chat_id]["current_question"] < len(asked_questions[chat_id]):
        send_question(chat_id)
    else:
        send_results_to_teacher(chat_id)
        bot.send_message(chat_id, f"Тест завершен. Вы ответили правильно на {user_data[chat_id]['correct_count']} из {len(asked_questions[chat_id])} вопросов.", reply_markup=types.ReplyKeyboardRemove())
        send_level_selection(chat_id)

def save_user_answer(chat_id, question_data, user_answer):
    user_details_query = "SELECT user_id, first_name, last_name, email FROM users WHERE chat_id = %s"
    cursor.execute(user_details_query, (chat_id,))
    user_details = cursor.fetchone()

    answer_data = (
        user_details[0],  # user_id
        question_data[0],  # question_id
        user_answer,
        user_answer == question_data[2][question_data[3]],  # is_correct
        user_details[1],  # first_name
        user_details[2],  # last_name
        user_details[3]  # email
    )

    insert_answer_query = """
    INSERT INTO user_answers (user_id, question_id, given_answer, is_correct, first_name, last_name, email)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(insert_answer_query, answer_data)
    conn.commit()


def send_results_to_teacher(chat_id):
    if chat_id not in student_answers or not student_answers[chat_id]:
        logging.info(f"No answers to send for chat_id {chat_id}")
        return

    # Загрузка данных пользователя
    cursor.execute("SELECT first_name, last_name, email FROM users WHERE chat_id = %s", (chat_id,))
    user_info = cursor.fetchone()
    if user_info is None:
        logging.error(f"No user found for chat_id {chat_id} in database")
        return

    first_name, last_name, email = user_info
    student_info = f"{first_name} {last_name}, Email: {email}"
    current_level = user_data[chat_id]['current_level']
    test_name = user_data[chat_id]['current_test']
    full_test_name = f"{current_level.capitalize()}-{test_name.capitalize()}"
    answers = student_answers[chat_id]
    correct_answers = [answer for answer in answers if answer['is_correct']]
    incorrect_answers = [answer for answer in answers if not answer['is_correct']]
    correct_details = "\n".join(
        [f"Вопрос: {a['question']}\nОтвет ученика: {a['user_answer']}\nПравильный ответ: {a['correct_answer']}" for a in
         correct_answers])
    incorrect_details = "\n".join(
        [f"Вопрос: {a['question']}\nОтвет ученика: {a['user_answer']}\nПравильный ответ: {a['correct_answer']}" for a in
         incorrect_answers])
    message = f"Ученик {student_info} прошел тест {full_test_name}.\nПравильные ответы ({len(correct_answers)}):\n{correct_details}\n\nНеправильные ответы ({len(incorrect_answers)}):\n{incorrect_details}"

    # Используем функцию для отправки длинных сообщений
    send_large_message(TEACHER_CHAT_ID, message)

def send_large_message(chat_id, message):
    """Разбивает и отправляет длинные сообщения по частям, если их длина превышает максимально допустимую."""
    MAX_LENGTH = 4096
    if len(message) > MAX_LENGTH:
        parts = [message[i:i + MAX_LENGTH] for i in range(0, len(message), MAX_LENGTH)]
        for part in parts:
            bot.send_message(chat_id, part)
    else:
        bot.send_message(chat_id, message)


if __name__ == '__main__':
    bot.polling(none_stop=True)


