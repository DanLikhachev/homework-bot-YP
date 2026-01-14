import logging
import os
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

logging.basicConfig(
    level=logging.DEBUG,
    filename="program.log",
)
logger = logging.getLogger(__name__)

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}
RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


class TokenError(Exception):
    """Ошибка отсутствия токенов."""

    pass


def check_tokens():
    """Проверка наличия обязательных переменных окружения."""
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    missing_tokens = [name for name, value in tokens.items() if not value]
    if missing_tokens:
        logger.critical(f'Отсутствуют токен(ы): {", ".join(missing_tokens)}')
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f"Сообщение отправлено: {message}")
        return True
    except Exception as error:
        logger.error(f"Сообщение не отправлено: {error}")
        return False


def get_api_answer(timestamp):
    """Отправка запроса к API Практикума."""
    params = {"from_date": timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        raise ConnectionError(f"Ошибка соединения с API: {error}")

    if response.status_code != HTTPStatus.OK:
        raise RuntimeError(
            f"Эндпоинт недоступен. Код ответа: {response.status_code}"
        )

    return response.json()


def check_response(response):
    """Проверка корректности ответа API."""
    if not isinstance(response, dict):
        raise TypeError("Ответ API не является словарём")

    if "homeworks" not in response:
        raise KeyError('В ответе отсутствует ключ "homeworks"')

    homeworks = response["homeworks"]

    if not isinstance(homeworks, list):
        raise TypeError('Значение "homeworks" не является списком')

    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if "homework_name" not in homework:
        raise KeyError('В ответе нет "homework_name"')

    homework_name = homework["homework_name"]
    status = homework.get("status")

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f"Ошибка статуса: {status}")

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical("Токен(ы) отсутствуют")
        raise TokenError("Токен(ы) отсутствуют")

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ""

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if homeworks:
                message = parse_status(homeworks[0])
                if send_message(bot, message):
                    timestamp = response.get("current_date", timestamp)
            else:
                logger.debug("Новых статусов нет")

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
            if message != last_error_message:
                if send_message(bot, message):
                    last_error_message = message

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
