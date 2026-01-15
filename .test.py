import pprint
import os
import requests
import time

from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_response():
    request = requests.get(
        url="https://practicum.yandex.ru/api/user_api/homework_statuses/",
        headers={"Authorization": f"OAuth {PRACTICUM_TOKEN}"},
        params={"from_date": 1}
    )
    return request.json()

pprint.pprint(get_response())