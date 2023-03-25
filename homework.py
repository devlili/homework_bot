import logging
import os
import sys
import time
from http import HTTPStatus
from typing import Any, Dict, List, NoReturn

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}


def check_tokens() -> bool:
    """Функция проверки доступности переменных окружения."""
    if not PRACTICUM_TOKEN or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.critical("Отсутсвует токен")
        raise Exception("Отсутсвует токен")
    else:
        return True


def send_message(bot: telegram.Bot, message: str) -> NoReturn:
    """Функция отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.debug("Успешная отправка сообщения в Telegram")
    except Exception as error:
        logging.error(f"Ошибка при отправке сообщения: {error}")
        raise ConnectionError(f"Ошибка при отправке сообщения: {error}")


def get_api_answer(timestamp: int) -> Dict[str, Any]:
    """Функция делает запрос к единственному эндпоинту API-сервиса."""
    payload = {"from_date": timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=payload, timeout=5
        )
    except requests.RequestException as error:
        logging.error(f"Ошибка при запросе к API: {error}")
        raise ConnectionError(f"Ошибка при запросе к API: {error}")
    status_code = homework_statuses.status_code
    if status_code != HTTPStatus.OK:
        logging.error(f"Ответ сервера: {status_code}")
        raise ConnectionError(f"Ответ сервера: {status_code}")

    return homework_statuses.json()


def check_response(response: Dict[str, Any]) -> List[Any]:
    """Функция проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logging.error("Данные приходят не в виде словаря")
        raise TypeError("Данные приходят не в виде словаря")
    if "homeworks" not in response:
        logging.error("Нет ключа 'homeworks'")
        raise TypeError("Нет ключа 'homeworks'")
    if not isinstance(response["homeworks"], list):
        logging.error("Данные приходят не в виде списка")
        raise TypeError("Данные приходят не в виде списка")

    return response.get("homeworks")


def parse_status(homework: Dict[str, Any]) -> str:
    """Функция извлекает статус о конкретной домашней работе."""
    homework_name = homework.get("homework_name")
    if not homework_name:
        logging.error("Нет ключа 'homework_name'")
        raise KeyError("Нет ключа 'homework_name'")
    verdict = HOMEWORK_VERDICTS.get(homework.get("status"))
    if not verdict:
        logging.error("API домашки возвращает недокументированный статус")
        raise KeyError("API домашки возвращает недокументированный статус")
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main() -> NoReturn:
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    old_message = ""
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = int(time.time())
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logging.debug("Нет новых данных")

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logging.critical(message)
            if message != old_message:
                send_message(bot, message)
            old_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
