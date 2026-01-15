import sys
import logging
import os
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot, apihelper


load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename="program.log",
)

logger = logging.getLogger(__name__)

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

sent_homework_statuses = {}


class TelegramConnectionError(Exception):
    """Ошибка отсутствия токенов."""


class TelegramRuntimeError(Exception):
    """Ошибка соединения с API."""


def check_tokens():
    """Проверка наличия обязательных переменных окружения."""
    tokens = {
        "PRACTICUM_TOKEN": PRACTICUM_TOKEN,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }
    missing_tokens = [name for name, value in tokens.items() if not value]
    if missing_tokens:
        logger.critical(f"Отсутствуют токен(ы): {", ".join(missing_tokens)}")
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except apihelper.ApiException as error:
        logger.error(f"Сообщение не отправлено: {error}")
    except requests.RequestException as error:
        logger.error(f"Сообщение не отправлено: {error}")
    else:
        logger.debug(f"Сообщение отправлено: {message}")


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
        raise KeyError('В ответе нет ключа "homework_name"')

    if "status" not in homework:
        raise KeyError('В ответе нет ключа "status"')

    homework_name = homework["homework_name"]
    status = homework["status"]

    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f"Неизвестный статус работы: {status}")

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical("Токен(ы) отсутствуют")
        sys.exit()

    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ""

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                homework_id = homeworks[0].get('id')

                if (homework_id
                    and homework_id in sent_homework_statuses
                    and sent_homework_statuses[homework_id] == message
                ):
                    logger.debug(f"{homework_id} уже был")
                    timestamp = response.get('current_date', timestamp)
                    continue
                
                if send_message(bot, message):
                    timestamp = response.get('current_date', timestamp)
                    sent_homework_statuses[homework_id] = message

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
