# 🚀 Деплой MAX-бота на Яндекс Cloud Functions + YDB

## Структура проекта

```
max_bot/
├── main.py          # Точка входа → handler(event, context)
├── config.py        # 4 переменные окружения
├── database.py      # YDB: создание таблиц + весь CRUD
├── handlers.py      # Вся логика бота
├── keyboards.py     # Клавиатуры
└── requirements.txt # requests, boto3
```

## Переменные окружения

| Ключ                 | Где взять                                      |
|----------------------|------------------------------------------------|
| `BOT_TOKEN`          | MAX → business.max.ru → Чат-боты → Интеграция |
| `YDB_DOCAPI_ENDPOINT`| YDB → консоль → Document API эндпоинт         |
| `INITIAL_ADMIN_ID`   | Ваш user_id в MAX (нужен 1 раз)                |

---

## Шаг 1 — Получить токен бота MAX

1. [business.max.ru](https://business.max.ru/self) → создать организацию → верификация
2. **Чат-боты** → **Создать бота** → дождаться модерации
3. **Интеграция** → **Получить токен** → скопировать

Ваш `user_id`: напишите боту `/start`, в логах Cloud Function найдите поле `sender.user_id`.

---

## Шаг 2 — Создать YDB

1. [console.cloud.yandex.ru](https://console.cloud.yandex.ru) → **Managed Service for YDB**
2. **Создать базу данных**:
   - Имя: `max-bot-db`
   - Тип: **Serverless** (платите только за запросы, идеально для бота)
3. После создания откройте БД → вкладка **Обзор**
4. Скопируйте **Document API эндпоинт**:
   ```
   https://docapi.serverless.yandexcloud.net/ru-central1/b1g.../etn...
   ```
   Это и есть `YDB_DOCAPI_ENDPOINT`.

> Таблицы создадутся **автоматически** при первом запуске функции.
> Вручную ничего создавать не нужно.

---

## Шаг 3 — Создать сервисный аккаунт

1. **IAM** → **Сервисные аккаунты** → **Создать**
2. Имя: `max-bot-sa`
3. Роли:
   - `ydb.editor` — читать и писать в YDB
   - `functions.functionInvoker` — вызывать функцию

---

## Шаг 4 — Создать Cloud Function

1. **Cloud Functions** → **Создать функцию** → имя `max-bot`
2. Вкладка **Редактор**:
   - Среда выполнения: **Python 3.12**
   - Загрузка: **ZIP-архив** → `max_bot.zip`
   - Точка входа: `main.handler`
   - Таймаут: `15 секунд`
   - Память: `256 МБ`
   - Сервисный аккаунт: `max-bot-sa`
3. Вкладка **Переменные окружения**:

| Ключ                  | Значение                                        |
|-----------------------|-------------------------------------------------|
| `BOT_TOKEN`           | токен из MAX                                    |
| `YDB_DOCAPI_ENDPOINT` | https://docapi.serverless.yandexcloud.net/...   |
| `INITIAL_ADMIN_ID`    | ваш user_id                                     |

---

## Шаг 5 — API Gateway

1. **API Gateway** → **Создать** → имя `max-bot-gw`
2. Спецификация (замените `FUNCTION_ID` и `SA_ID`):

```yaml
openapi: "3.0.0"
info:
  title: MAX Bot
  version: "1.0"
paths:
  /webhook:
    post:
      operationId: webhook
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: FUNCTION_ID
        service_account_id: SA_ID
      responses:
        "200":
          description: OK
```

3. Скопируйте URL: `https://xxxxxx.apigw.yandexcloud.net`

---

## Шаг 6 — Зарегистрировать Webhook в MAX

```bash
curl -X POST "https://platform-api.max.ru/subscriptions" \
  -H "Authorization: ВАШ_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://xxxxxx.apigw.yandexcloud.net/webhook",
    "update_types": ["message_created", "message_callback", "bot_started"]
  }'
```

Ответ: `{"success": true}`

---

## Шаг 7 — Проверка

1. Напишите боту `/start` → приветствие + 4 кнопки
2. Кнопка «🔍 Получить ID» → user_id, chat_id, message_id
3. `/admin` → панель администратора
4. Измените текст кнопки → проверьте в YDB консоли таблицу `bot_config`
5. Логи: **Cloud Functions** → **Журнал**

---

## Что хранится в YDB

| Таблица        | Что хранит                                    |
|----------------|-----------------------------------------------|
| `bot_config`   | Приветствие, названия 4 кнопок, текст контактов |
| `contacts_links` | Ссылки в разделе Контакты (добавляются из админки) |
| `admins`       | user_id администраторов                       |
| `admin_states` | Временные FSM-состояния при редактировании    |

## Упаковка в ZIP

```bash
cd max_bot/
zip -r ../max_bot.zip . -x "*.pyc" -x "__pycache__/*"
```

---

## Как дорабатывать бота

Нужна новая функция? Алгоритм простой:

1. **Новые данные** → добавить таблицу или поле в `database.py`
2. **Новая кнопка** → добавить в `keyboards.py` и в `handlers.py`
3. **Новый экран** → добавить функцию `_screen_xxx` в `handlers.py`
4. Переупаковать ZIP, загрузить новую версию функции

База данных и все накопленные данные остаются нетронутыми.
