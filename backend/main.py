
import os
import random 
import secrets
import hmac
import hashlib
import json
import httpx
from urllib.parse import parse_qsl
from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def send_telegram_message(telegram_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False

    url = (
        f"https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    try:
        response = httpx.post(
            url,
            json={
                "chat_id": telegram_id,
                "text": text
            },
            timeout=10
        )

        return (
            response.is_success
            and response.json().get("ok", False)
        )

    except Exception:
        return False

def verify_telegram_data(init_data: str):
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Telegram token не настроен")

    data = dict(parse_qsl(init_data, keep_blank_values=True))

    received_hash = data.pop("hash", None)

    if not received_hash:
        raise HTTPException(status_code=401, detail="Нет подписи Telegram")

    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(data.items())
    )

    secret_key = hmac.new(
        b"WebAppData",
        TELEGRAM_BOT_TOKEN.encode(),
        hashlib.sha256
    ).digest()

    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=401, detail="Проверка Telegram не пройдена")

    auth_date = int(data.get("auth_date", "0"))

    if time.time() - auth_date > 86400:
        raise HTTPException(status_code=401, detail="Данные Telegram устарели")

    user = json.loads(data.get("user", "{}"))

    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Не найден Telegram ID")

    return user

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:
    raise RuntimeError("Не задан пароль администратора в .env")

security = HTTPBasic()

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Не найдены настройки Supabase в .env")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)
def verify_admin(
    credentials: HTTPBasicCredentials = Depends(security)
):
    correct_username = secrets.compare_digest(
        credentials.username,
        "admin"
    )

    correct_password = secrets.compare_digest(
        credentials.password,
        ADMIN_PASSWORD
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic"}
        )

    return True

app = FastAPI(title="Тайный Санта")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


from pydantic import BaseModel, Field

class Participant(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    telegram: str = Field(default="", max_length=40)
    wishes: str = Field(default="", max_length=500)
    initData: str = Field(default="", max_length=5000)


@app.get("/")
def home():
    return {
        "message": "Тайный Санта подключён!",
        "status": "ok"
    }


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/settings")
def get_settings():
    response = supabase.table("game_settings") \
        .select("*") \
        .eq("id", 1) \
        .single() \
        .execute()

    return response.data
    

@app.get("/admin/settings")
def admin_settings(admin: bool = Depends(verify_admin)):
    response = supabase.table("game_settings") \
        .select("*") \
        .eq("id", 1) \
        .single() \
        .execute()
    
    return response.data
   
@app.post("/admin/registration")
def change_registration(
    is_open: bool,
    admin: bool = Depends(verify_admin)
):
    response = supabase.table("game_settings").update({
        "registration_open": is_open
    }).eq("id", 1).execute()

    return {
        "success": True,
        "registration_open": is_open,
        "message": "Регистрация открыта!" if is_open else "Регистрация закрыта!"
    } 


@app.post("/register")
def register_participant(participant: Participant):
    name = participant.name.strip()
    telegram = participant.telegram.strip()
    wishes = participant.wishes.strip()
    init_data = participant.initData

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Укажи своё имя"
        )

    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="Открой сайт через Telegram"
        )

    # Проверяем подлинность данных Telegram
    user = verify_telegram_data(init_data)
    telegram_id = str(user["id"])

    try:
        settings = supabase.table("game_settings") \
            .select("registration_open") \
            .eq("id", 1) \
            .single() \
            .execute()

        if not settings.data["registration_open"]:
            raise HTTPException(
                status_code=403,
                detail="Регистрация сейчас закрыта!"
            )

        supabase.table("participants").insert({
            "name": name,
            "telegram_id": telegram_id,
            "telegram_username": telegram,
            "wishes": wishes
            
        }).execute()

        send_telegram_message(
            telegram_id,
            f"🎄 Поздравляем, {name}!\n\n"
            "Ты официально участвуешь в игре "
            "«Тайный Санта»!\n\n"
            "🎁 Бюджет подарка: до 1 000 ₽.\n\n"
            "✨ Ожидай начала жеребьёвки!\n"
            "🤫 Не раскрывай свою личность."
        )

        return {
            "success": True,
            "message": "Ты зарегистрирован!"
        }

    except HTTPException:
        raise

    except Exception as error:
        error_text = str(error)

        if "23505" in error_text:
            raise HTTPException(
                status_code=409,
                detail="Этот Telegram уже зарегистрирован!"
            )

        raise HTTPException(
            status_code=500,
            detail="Не удалось сохранить регистрацию"
        )

        
@app.get("/admin/participants")
def get_all_participants(
    admin: bool = Depends(verify_admin)
):
    response = supabase.table("participants") \
        .select("name, telegram_username, wishes") \
        .execute()

    return {
        "participants": response.data,
        "total": len(response.data)
    }
    
@app.post("/admin/draw")
def draw_secret_santa(
    admin: bool = Depends(verify_admin)
):
    # Получаем участников
    response = supabase.table("participants") \
        .select("name, telegram_username") \
        .execute()

    participants = response.data

    # Проверяем количество участников
    if len(participants) < 2:
        raise HTTPException(
            status_code=400,
            detail="Для жеребьёвки нужно минимум 2 участника"
        )

    # Проверяем Telegram участников
    usernames = [
        p["telegram_username"].strip()
        for p in participants
        if p.get("telegram_username")
    ]

    if len(usernames) != len(participants):
        raise HTTPException(
            status_code=400,
            detail="У всех участников должен быть указан Telegram"
        )

    # Проверяем, не проводилась ли уже жеребьёвка
    existing = supabase.table("assignments") \
        .select("id") \
        .limit(1) \
        .execute()

    
    
    if existing.data:
        raise HTTPException(
            status_code=409,
            detail="Жеребьёвка уже проведена!"
        )

    # Перемешиваем участников
    random.shuffle(usernames)

    # Выбираем случайный сдвиг по кругу
    shift = random.randrange(1, len(usernames))

    # Создаём получателей по кругу
    receivers = usernames[shift:] + usernames[:shift]

    # Создаём пары
    assignments = [
        {
            "giver_telegram_username": giver,
            "receiver_telegram_username": receiver
        }
        for giver, receiver in zip(usernames, receivers)
    ]

    # Сохраняем результаты
    supabase.table("assignments").insert(
        assignments
    ).execute()

    return {
        "success": True,
        "message": "Жеребьёвка успешно проведена!",
        "total": len(assignments)
    }



@app.post("/visit")
def register_visit():
    try:
        supabase.table("site_visits").insert({}).execute()

        return {
            "success": True,
            "message": "Посещение учтено"
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Не удалось учесть посещение"
        )


@app.post("/telegram-visit")
def telegram_visit(data: dict):
    init_data = data.get("initData", "")

    if not init_data:
        raise HTTPException(
            status_code=401,
            detail="Нет данных Telegram"
        )

    user = verify_telegram_data(init_data)
    telegram_id = user["id"]
    

    try:
        participant = (
            supabase.table("participants")
            .select("id, name")
            .eq("telegram_id", telegram_id)
            .execute()
        )

        if not participant.data:
            return {
                "success": False,
                "message": "Участник пока не привязан к Telegram"
            }

        supabase.table("site_visits").insert({
            "telegram_id": telegram_id
        }).execute()

        return {
            "success": True,
            "message": "Посещение участника записано"
        }

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Не удалось записать посещение"
        )
        
@app.post("/admin/test-message")
def test_message(
    telegram_id: int,
    admin: bool = Depends(verify_admin)
):
    sent = send_telegram_message(
        telegram_id,
        "🎅 Привет! Это тестовое сообщение "
        "от твоего Тайного Санты!\n\n"
        "🎄 Наш бот работает!"
    )

    return {"success": sent}

from fastapi import Header

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")


@app.post("/telegram-webhook")
def telegram_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: str = Header(default="")
):
    if not WEBHOOK_SECRET or not secrets.compare_digest(
        x_telegram_bot_api_secret_token,
        WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Access denied"
        )

    message = update.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")

    if chat_id and chat.get("type") == "private":
        if text.split()[:1] == ["/start"]:
            send_telegram_message(
                chat_id,
                "🎄 Добро пожаловать в игру "
                "«Тайный Санта»!\n\n"
                "✨ Стань частью новогоднего волшебства!\n\n"
                "🎁 Бюджет подарка: до 1 000 ₽.\n\n"
                "💌 Зарегистрируйся и оставь пожелания.\n\n"
                "🎅 Открыть игру:\n"
                "https://t.me/TheNewYearIsNear_bot/SecretSanta"
            )

    return {"ok": True}
