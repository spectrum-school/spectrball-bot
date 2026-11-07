import asyncio
import logging
import json
import os
import random

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

from maxapi import Bot, Dispatcher, F
from maxapi.filters.command import CommandStart
from maxapi.types import BotStarted, MessageCreated
from maxapi.types.attachments.buttons import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

# ================= НАСТРОЙКИ =================
try:
    with open('token.max', encoding='utf-8') as f:
        BOT_TOKEN = f.read().strip()
except FileNotFoundError:
    raise SystemExit(
        "❌ Файл token.max не найден.\n"
        "Создайте его в корне проекта и поместите туда токен бота из MAX."
    ) from None

if not BOT_TOKEN:
    raise SystemExit("❌ Файл token.max пуст. Вставьте в него токен бота из MAX.")

SCHOOLS_DIR = "schools"
SCHOOL_NAME = "school_1"
DEFAULT_CLASS = "class_7a.json"
CONFIG_FILE = "config.json"

# Состояния: {chat_id: {"state": ..., "class_file": ..., ...}}
user_states = {}

SHOP_ITEMS = {
    "1": ("Ответить с места", 5),
    "2": ("Выбрать музыку на перемене", 10),
    "3": ("+1 день к дедлайну ДЗ", 10),
    "4": ("Сменить место на день", 15),
    "5": ("Право выбрать тему классного часа", 20),
    "6": ("Освобождение от устного ответа", 25),
    "7": ("Провести фрагмент урока (5-7 мин)", 40),
}


# ================= РАБОТА С КЛАССАМИ =================
def list_classes():
    school_path = os.path.join(SCHOOLS_DIR, SCHOOL_NAME)
    if not os.path.isdir(school_path):
        return []
    return sorted(
        f for f in os.listdir(school_path)
        if f.startswith("class_") and f.endswith(".json")
    )


def class_display_name(cf):
    name = cf.replace("class_", "").replace(".json", "")
    return name.upper() + " класс"


def _pot_path(class_file):
    """pot_7a.json для class_7a.json"""
    name = class_file.replace("class_", "pot_", 1)
    return os.path.join(SCHOOLS_DIR, SCHOOL_NAME, name)


def init_data():
    os.makedirs(os.path.join(SCHOOLS_DIR, SCHOOL_NAME), exist_ok=True)

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"current_school": SCHOOL_NAME, "current_class": DEFAULT_CLASS}, f)

    class_path = os.path.join(SCHOOLS_DIR, SCHOOL_NAME, DEFAULT_CLASS)
    if not os.path.exists(class_path):
        save_class_data(DEFAULT_CLASS, [
            {"id": "1111", "name": "Иванов Сергей", "balance": 20, "role": "student", "chat_id": None, "purchases": []},
            {"id": "2222", "name": "Петрова Анна", "balance": 60, "role": "student", "chat_id": None, "purchases": []},
            {"id": "3333", "name": "Сидоров Максим", "balance": 150, "role": "student", "chat_id": None, "purchases": []},
            {"id": "4444", "name": "Кузнецова Ольга", "balance": 320, "role": "student", "chat_id": None, "purchases": []},
            {"id": "9999", "name": "Учитель", "balance": 0, "role": "teacher", "chat_id": None, "purchases": []},
        ])
        logging.info(f"Создан демо-класс {DEFAULT_CLASS}")

    pot_path = _pot_path(DEFAULT_CLASS)
    if not os.path.exists(pot_path):
        with open(pot_path, 'w', encoding='utf-8') as f:
            json.dump(
                {"current": 0, "goal": 500, "description": "Кино вместо урока"},
                f, ensure_ascii=False, indent=4,
            )


def load_class_data(class_file):
    path = os.path.join(SCHOOLS_DIR, SCHOOL_NAME, class_file)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_class_data(class_file, data):
    path = os.path.join(SCHOOLS_DIR, SCHOOL_NAME, class_file)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_pot(class_file):
    path = _pot_path(class_file)
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(
                {"current": 0, "goal": 500, "description": "Кино вместо урока"},
                f, ensure_ascii=False, indent=4,
            )
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_pot(class_file, pot):
    path = _pot_path(class_file)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(pot, f, ensure_ascii=False, indent=4)


def find_user_by_chat_id(chat_id):
    for cf in list_classes():
        for u in load_class_data(cf):
            if u.get('chat_id') == chat_id:
                return u, cf
    return None, None


def get_user_by_code(class_file, code):
    users = load_class_data(class_file)
    return next((u for u in users if u['id'] == code), None)


def get_teacher_chat_id(class_file):
    users = load_class_data(class_file)
    t = next((u for u in users if u['role'] == 'teacher' and u.get('chat_id')), None)
    return t['chat_id'] if t else None


def generate_unique_code(class_file):
    """Возвращает 4-значный код, которого ещё нет в классе."""
    users = load_class_data(class_file)
    existing = {u['id'] for u in users}
    for _ in range(1000):
        code = str(random.randint(1000, 9999))
        if code not in existing:
            return code
    raise RuntimeError("Не удалось сгенерировать уникальный код — класс переполнен.")


def get_status(b):
    return (
        "👑 ЛЕГЕНДА" if b >= 300 else
        "🔥 ЛИДЕР" if b >= 151 else
        "⚡ АКТИВИСТ" if b >= 51 else
        "🥚 НОВИЧОК"
    )


# ================= КЛАВИАТУРЫ =================
def make_keyboard(rows):
    kb = InlineKeyboardBuilder()
    for row in rows:
        for text, payload in row:
            kb.add(CallbackButton(text=text, payload=payload))
        kb.row()
    return kb.as_markup()


def kb_classes():
    rows = [[(class_display_name(cf), f"class|{cf}")] for cf in list_classes()]
    return make_keyboard(rows)


def kb_role():
    return make_keyboard([
        [("🎓 Я ученик", "role_student")],
        [("👨‍🏫 Я учитель", "role_teacher")],
        [("🔙 Назад", "back_start")],
    ])


def kb_identity(class_file, role):
    users = load_class_data(class_file)
    rows = [[(u['name'], f"login|{class_file}|{u['id']}")] for u in users
            if u['role'] == role and not u.get('chat_id')]
    rows.append([("🔙 Назад", "back_class")])
    return make_keyboard(rows)


def kb_student_menu():
    return make_keyboard([
        [("💰 Мой баланс", "menu_balance"), ("🛒 Магазин", "menu_shop")],
        [("🏺 Общий котёл", "menu_pot"), ("🤝 Перевести баллы", "menu_transfer")],
        [("🎁 Мои привилегии", "menu_my_purchases")],
    ])


def kb_teacher_menu():
    return make_keyboard([
        [("➕ Начислить баллы", "menu_award")],
        [("📋 Список класса", "menu_list")],
        [("🎁 Все привилегии", "menu_all_purchases")],
        [("🏺 Общий котёл", "menu_teacher_pot")],
        [("👥 Управление учениками", "menu_manage_students")],
    ])


def kb_manage_students():
    return make_keyboard([
        [("➕ Добавить ученика", "manage_add")],
        [("🗑 Удалить ученика", "manage_delete")],
        [("🔙 В меню", "back_menu")],
    ])


def kb_delete_targets(class_file):
    users = load_class_data(class_file)
    rows = [[(u['name'], f"del_student|{class_file}|{u['id']}")] for u in users
            if u['role'] == 'student']
    rows.append([("🔙 Назад", "menu_manage_students")])
    return make_keyboard(rows)


def kb_confirm_delete(class_file, code, name):
    return make_keyboard([
        [("✅ Да, удалить", f"confirm_del_student|{class_file}|{code}")],
        [("❌ Отмена", "menu_manage_students")],
    ])


def kb_shop():
    rows = [[(f"{name} — {price} б.", f"buy_{k}")] for k, (name, price) in SHOP_ITEMS.items()]
    rows.append([("🔙 В меню", "back_menu")])
    return make_keyboard(rows)


def kb_transfer_choice(class_file):
    return make_keyboard([
        [("👥 Однокласснику", f"transfer_mode_person|{class_file}")],
        [("🏺 В общий котёл", f"transfer_mode_pot|{class_file}")],
        [("🔙 В меню", "back_menu")],
    ])


def kb_teacher_pot():
    return make_keyboard([
        [("➕ Пополнить котёл", "teacher_pot_add")],
        [("🔙 В меню", "back_menu")],
    ])


def kb_transfer_targets(class_file, exclude_id):
    users = load_class_data(class_file)
    rows = [[(u['name'], f"transfer_{u['id']}")] for u in users
            if u['role'] == 'student' and u['id'] != exclude_id]
    rows.append([("🔙 Назад", "menu_transfer")])
    return make_keyboard(rows)


def kb_award_targets(class_file):
    users = load_class_data(class_file)
    rows = [[(u['name'], f"award_{u['id']}")] for u in users if u['role'] == 'student']
    rows.append([("🔙 В меню", "back_menu")])
    return make_keyboard(rows)


def kb_award_amounts(tid):
    return make_keyboard([
        [("+1", f"give_{tid}_1"), ("+5", f"give_{tid}_5"), ("+10", f"give_{tid}_10")],
        [("+20", f"give_{tid}_20"), ("+50", f"give_{tid}_50")],
        [("🔙 Назад", "menu_award")],
    ])


def kb_back_menu():
    return make_keyboard([[("🔙 В меню", "back_menu")]])


def kb_my_purchases():
    return make_keyboard([[("🔙 В меню", "back_menu")]])


def kb_all_purchases(class_file, purchases):
    rows = []
    for p in purchases:
        label = f"✅ {p['user_name']}: {p['item']} ({p['price']} б.)"
        rows.append([(label, f"del_purchase|{class_file}|{p['code']}|{p['item']}")])
    rows.append([("🔙 В меню", "back_menu")])
    return make_keyboard(rows)


# ================= ИНИЦИАЛИЗАЦИЯ =================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ================= УТИЛИТЫ =================
def get_chat_id(event):
    paths = [
        lambda e: e.message.recipient.chat_id,
        lambda e: e.callback.message.recipient.chat_id,
        lambda e: e.message.chat.chat_id,
        lambda e: e.message.chat_id,
        lambda e: e.chat.chat_id,
        lambda e: e.chat_id,
    ]
    for path in paths:
        try:
            v = path(event)
            if v:
                return v
        except AttributeError:
            continue
    return None


def get_payload(event):
    paths = [
        lambda e: e.payload,
        lambda e: e.callback.payload,
        lambda e: e.data,
        lambda e: e.callback.data,
        lambda e: e.callback_data,
    ]
    for path in paths:
        try:
            v = path(event)
            if v:
                return v
        except AttributeError:
            continue
    return None


async def reply(event, text, keyboard=None):
    chat_id = get_chat_id(event)
    if not chat_id:
        logging.error("[reply] chat_id не найден")
        return
    try:
        kwargs = {"chat_id": chat_id, "text": text}
        if keyboard:
            kwargs["attachments"] = [keyboard]
        await bot.send_message(**kwargs)
        logging.info(f"[reply] → chat={chat_id} text={text[:40]!r} kb={'yes' if keyboard else 'no'}")
    except Exception as e:
        logging.error(f"[reply] failed: {type(e).__name__}: {e}")


def get_all_purchases(class_file):
    users = load_class_data(class_file)
    purchases = []
    for u in users:
        for p in u.get('purchases', []):
            purchases.append({
                "code": u['id'],
                "user_name": u['name'],
                "item": p['item'],
                "price": p['price'],
                "used": p.get('used', False),
            })
    return purchases


# ================= /start =================
@dp.bot_started()
async def on_bot_started(event: BotStarted):
    await bot.send_message(chat_id=event.chat_id, text="Привет! Я бот «СпектрБалл».\nНапишите /start")


@dp.message_created(CommandStart())
async def cmd_start(event: MessageCreated):
    chat_id = get_chat_id(event)
    user, cf = find_user_by_chat_id(chat_id)
    logging.info(f"[START] chat={chat_id} user={user['name'] if user else 'NO_USER'} class={cf}")
    if user:
        kb = kb_student_menu() if user['role'] == 'student' else kb_teacher_menu()
        await reply(event, f"С возвращением, {user['name']}!\nКласс: {class_display_name(cf)}\nВыберите действие:", kb)
    else:
        user_states[chat_id] = {"state": "waiting_class"}
        await reply(event, "👋 Добро пожаловать в **СпектрБалл**!\nВыберите класс:", kb_classes())


# ================= CALLBACK =================
@dp.message_callback()
async def handle_callback(event):
    data = get_payload(event)
    chat_id = get_chat_id(event)
    user, cf = find_user_by_chat_id(chat_id)
    state = user_states.get(chat_id, {})
    logging.info(f"[CB] chat={chat_id} payload={data} user={user['name'] if user else 'NO_USER'} state={state.get('state')}")

    if not data:
        logging.warning("[CB] нет payload.")
        return

    # ---- ВЫБОР КЛАССА ----
    if data.startswith("class|"):
        cf_sel = data.split("|", 1)[1]
        if cf_sel not in list_classes():
            return await reply(event, "Класс не найден.", kb_classes())
        user_states[chat_id] = {"state": "waiting_role", "class_file": cf_sel}
        await reply(event, f"Класс: {class_display_name(cf_sel)}\nВыберите роль:", kb_role())

    # ---- ВЫБОР РОЛИ ----
    elif data in ("role_student", "role_teacher"):
        cf_sel = state.get("class_file")
        if not cf_sel:
            return await reply(event, "Сначала выберите класс.", kb_classes())
        role = "student" if data == "role_student" else "teacher"
        user_states[chat_id].update({"state": "waiting_identity", "role": role})
        label = "ученики" if role == "student" else "учителя"
        await reply(event, f"Выберите себя ({label}, {class_display_name(cf_sel)}):", kb_identity(cf_sel, role))

    elif data == "back_start":
        user_states[chat_id] = {"state": "waiting_class"}
        await reply(event, "Выберите класс:", kb_classes())

    elif data == "back_class":
        cf_sel = state.get("class_file")
        if not cf_sel:
            user_states[chat_id] = {"state": "waiting_class"}
            return await reply(event, "Выберите класс:", kb_classes())
        user_states[chat_id]["state"] = "waiting_role"
        await reply(event, f"Класс: {class_display_name(cf_sel)}\nВыберите роль:", kb_role())

    # ---- ВЫБОР ИМЕНИ ----
    elif data.startswith("login|"):
        parts = data.split("|")
        if len(parts) < 3:
            return await reply(event, "Ошибка формата.", kb_role())
        cf_sel, code = parts[1], parts[2]
        target = get_user_by_code(cf_sel, code)
        if not target:
            return await reply(event, "Профиль не найден.", kb_role())
        user_states[chat_id] = {
            "state": "waiting_code",
            "class_file": cf_sel,
            "code": code,
            "role": target['role'],
        }
        await reply(
            event,
            f"🔐 Вы выбрали профиль: **{target['name']}**\n\n"
            f"Для подтверждения введите **4-значный код** этого профиля "
            f"(например, 1111). Код выдаёт учитель или классный руководитель.\n\n"
            f"❗ Вводить код нужно **один раз** — при первой регистрации. "
            f"В дальнейшем вход будет выполняться автоматически.",
            kb_back_menu(),
        )

    # ---- ВОЗВРАТ В МЕНЮ ----
    elif data == "back_menu":
        user_states.pop(chat_id, None)
        if user:
            kb = kb_student_menu() if user['role'] == 'student' else kb_teacher_menu()
            await reply(event, "📱 Меню:", kb)
        else:
            user_states[chat_id] = {"state": "waiting_class"}
            await reply(event, "Начните заново:", kb_classes())

    # ---- УЧЕНИК ----
    elif data == "menu_balance" and user:
        await reply(event, f"👤 {user['name']}\n💰 {user['balance']} б.\n🎖 {get_status(user['balance'])}", kb_back_menu())

    elif data == "menu_shop" and user:
        await reply(event, "🛒 Магазин:", kb_shop())

    elif data.startswith("buy_") and user and cf:
        key = data.split("_", 1)[1]
        if key not in SHOP_ITEMS:
            return
        name, price = SHOP_ITEMS[key]
        if user['balance'] < price:
            return await reply(event, f"❌ Нужно {price}, у вас {user['balance']}.", kb_back_menu())
        users = load_class_data(cf)
        for u in users:
            if u['id'] == user['id']:
                u['balance'] -= price
                u.setdefault('purchases', []).append({"item": name, "price": price, "used": False})
                break
        save_class_data(cf, users)
        tid = get_teacher_chat_id(cf)
        if tid:
            try:
                await bot.send_message(chat_id=tid, text=f"🔔 {user['name']} купил {name} за {price} б.")
            except Exception as e:
                logging.warning(f"[notify] {e}")
        await reply(event, f"✅ {name}\nСписано {price} б.\nОстаток {user['balance'] - price} б.", kb_back_menu())

    # ---- ПЕРЕВОД ----
    elif data == "menu_transfer" and user and cf:
        await reply(event, "🤝 **Перевод баллов**\n\nВыберите, куда перевести:", kb_transfer_choice(cf))

    elif data.startswith("transfer_mode_person|") and user and cf:
        await reply(event, "👥 Выберите одноклассника:", kb_transfer_targets(cf, user['id']))

    elif data.startswith("transfer_mode_pot|") and user and cf:
        pot = load_pot(cf)
        max_transfer = int(user['balance'] * 0.3)
        user_states[chat_id] = {"state": "waiting_pot_amount", "class_file": cf, "user_id": user['id']}
        await reply(
            event,
            f"🏺 **Перевод в общий котёл**\n\n"
            f"Текущая цель: {pot['description']}\n"
            f"Собрано: {pot['current']} / {pot['goal']} б.\n\n"
            f"💰 Ваш баланс: {user['balance']} б.\n"
            f"Можно перевести не более {max_transfer} б. (30% от баланса).\n\n"
            f"✏️ Введите число — сколько баллов перевести в котёл:",
            kb_back_menu(),
        )

    elif data.startswith("transfer_") and user and cf and not data.startswith("transfer_mode_"):
        tid = data.split("_", 1)[1]
        target = get_user_by_code(cf, tid)
        if not target:
            return
        mx = int(user['balance'] * 0.3)
        user_states[chat_id] = {"state": "waiting_transfer_amount", "class_file": cf, "target_id": tid}
        await reply(
            event,
            f"🤝 **Перевод ученику**\n\n"
            f"Кому: **{target['name']}**\n"
            f"Ваш баланс: {user['balance']} б.\n"
            f"Максимум к переводу: {mx} б. (30% от вашего баланса).\n\n"
            f"✏️ Введите число — сколько баллов перевести:",
            kb_back_menu(),
        )

    elif data == "menu_pot" and cf:
        pot = load_pot(cf)
        await reply(
            event,
            f"🏺 **Общий котёл класса**\n\n"
            f"Цель: {pot['description']}\n"
            f"Прогресс: {pot['current']} / {pot['goal']} б.\n"
            f"Осталось собрать: {max(0, pot['goal'] - pot['current'])} б.",
            kb_back_menu(),
        )

    # ---- МОИ ПРИВИЛЕГИИ (УЧЕНИК) ----
    elif data == "menu_my_purchases" and user:
        purchases = user.get('purchases', [])
        if not purchases:
            text = "🎁 **Мои привилегии**\n\nУ вас пока нет купленных привилегий."
        else:
            text = "🎁 **Мои привилегии**\n\n"
            for i, p in enumerate(purchases, 1):
                status = "✅ использована" if p.get('used') else "⏳ активна"
                text += f"{i}. {p['item']} — {p['price']} б. ({status})\n"
        await reply(event, text, kb_my_purchases())

    # ---- УЧИТЕЛЬ ----
    elif data == "menu_award" and user and user['role'] == 'teacher' and cf:
        await reply(event, "Кому начислить?", kb_award_targets(cf))

    elif data.startswith("award_") and user and user['role'] == 'teacher' and cf:
        tid = data.split("_", 1)[1]
        target = get_user_by_code(cf, tid)
        if not target:
            return
        await reply(event, f"Сколько: {target['name']}?", kb_award_amounts(tid))

    elif data.startswith("give_") and user and user['role'] == 'teacher' and cf:
        parts = data.split("_")
        if len(parts) < 3:
            return
        tid, amount_raw = parts[1], parts[2]
        try:
            amount = int(amount_raw)
        except ValueError:
            return
        users = load_class_data(cf)
        target = next((u for u in users if u['id'] == tid), None)
        if not target:
            return
        target['balance'] += amount
        save_class_data(cf, users)
        await reply(event, f"✅ {target['name']} +{amount} б.\nБаланс: {target['balance']} б.", kb_back_menu())

    elif data == "menu_list" and user and user['role'] == 'teacher' and cf:
        users = load_class_data(cf)
        text = f"📋 Список класса ({class_display_name(cf)}):\n\n"
        for u in sorted(users, key=lambda x: x['balance'], reverse=True):
            if u['role'] == 'student':
                text += f"👤 {u['name']} — {u['balance']} б. ({get_status(u['balance'])})\n"
        await reply(event, text, kb_back_menu())

    elif data == "menu_teacher_pot" and user and user['role'] == 'teacher' and cf:
        pot = load_pot(cf)
        progress = int(pot['current'] / pot['goal'] * 100) if pot['goal'] > 0 else 0
        await reply(
            event,
            f"🏺 **Общий котёл класса**\n\n"
            f"Цель: {pot['description']}\n"
            f"Собрано: {pot['current']} / {pot['goal']} б. ({progress}%)\n"
            f"Осталось: {max(0, pot['goal'] - pot['current'])} б.",
            kb_teacher_pot(),
        )

    elif data == "teacher_pot_add" and user and user['role'] == 'teacher' and cf:
        pot = load_pot(cf)
        user_states[chat_id] = {"state": "waiting_teacher_pot_amount", "class_file": cf}
        await reply(
            event,
            f"✏️ **Пополнение котла**\n\n"
            f"Текущее состояние: {pot['current']} / {pot['goal']} б.\n\n"
            f"Введите число — на сколько баллов пополнить котёл:",
            kb_back_menu(),
        )

    elif data == "menu_all_purchases" and user and user['role'] == 'teacher' and cf:
        purchases = get_all_purchases(cf)
        if not purchases:
            return await reply(event, "🎁 Пока никто не покупал привилегии.", kb_back_menu())
        text = f"🎁 **Все привилегии класса ({class_display_name(cf)})**\n\n"
        text += "Нажмите на привилегию, чтобы отметить её использованной:\n\n"
        for p in purchases:
            status = "✅" if p.get('used') else "⏳"
            text += f"{status} {p['user_name']}: {p['item']} ({p['price']} б.)\n"
        await reply(event, text, kb_all_purchases(cf, [p for p in purchases if not p.get('used')]))

    elif data.startswith("del_purchase|") and user and user['role'] == 'teacher' and cf:
        parts = data.split("|")
        if len(parts) < 4:
            return
        cf_sel, code, item = parts[1], parts[2], parts[3]
        users = load_class_data(cf_sel)
        removed = False
        for u in users:
            if u['id'] == code:
                new_purchases = []
                for p in u.get('purchases', []):
                    if not removed and p['item'] == item and not p.get('used', False):
                        removed = True
                        continue
                    new_purchases.append(p)
                u['purchases'] = new_purchases
                break
        save_class_data(cf_sel, users)
        purchases = get_all_purchases(cf_sel)
        if not purchases:
            await reply(event, "✅ Привилегия отмечена использованной. Список пуст.", kb_back_menu())
        else:
            text = "✅ Привилегия отмечена использованной.\n\n"
            text += f"Осталось активных: {len([p for p in purchases if not p.get('used')])}\n"
            await reply(event, text, kb_all_purchases(cf_sel, [p for p in purchases if not p.get('used')]))

    # ---- УПРАВЛЕНИЕ УЧЕНИКАМИ ----
    elif data == "menu_manage_students" and user and user['role'] == 'teacher' and cf:
        await reply(event, "👥 **Управление учениками**\n\nВыберите действие:", kb_manage_students())

    elif data == "manage_add" and user and user['role'] == 'teacher' and cf:
        user_states[chat_id] = {"state": "waiting_new_student_name", "class_file": cf}
        await reply(
            event,
            "✏️ **Добавление ученика**\n\n"
            "Введите имя и фамилию ученика (например, «Иванов Иван»).\n\n"
            "Бот автоматически присвоит ему уникальный 4-значный код для входа.",
            kb_back_menu(),
        )

    elif data == "manage_delete" and user and user['role'] == 'teacher' and cf:
        users = load_class_data(cf)
        students = [u for u in users if u['role'] == 'student']
        if not students:
            return await reply(event, "В классе нет учеников для удаления.", kb_manage_students())
        await reply(event, "🗑 Кого удалить?", kb_delete_targets(cf))

    elif data.startswith("del_student|") and user and user['role'] == 'teacher' and cf:
        parts = data.split("|")
        if len(parts) < 3:
            return
        cf_sel, code = parts[1], parts[2]
        target = get_user_by_code(cf_sel, code)
        if not target or target['role'] != 'student':
            return await reply(event, "Ученик не найден.", kb_manage_students())
        await reply(
            event,
            f"🗑 **Удаление ученика**\n\n"
            f"Вы уверены, что хотите удалить **{target['name']}**?\n"
            f"Его баланс ({target['balance']} б.) и привилегии будут потеряны.\n\n"
            f"Действие необратимо.",
            kb_confirm_delete(cf_sel, code, target['name']),
        )

    elif data.startswith("confirm_del_student|") and user and user['role'] == 'teacher' and cf:
        parts = data.split("|")
        if len(parts) < 3:
            return
        cf_sel, code = parts[1], parts[2]
        users = load_class_data(cf_sel)
        new_users = [u for u in users if not (u['id'] == code and u['role'] == 'student')]
        if len(new_users) == len(users):
            return await reply(event, "Ученик уже удалён.", kb_manage_students())
        save_class_data(cf_sel, new_users)
        await reply(event, f"✅ Ученик с кодом {code} удалён.", kb_manage_students())


# ================= ТЕКСТ =================
@dp.message_created(F.message.body.text == "/whoid")
async def cmd_whoid(event: MessageCreated):
    chat_id = get_chat_id(event)
    user, cf = find_user_by_chat_id(chat_id)
    state = user_states.get(chat_id)
    await reply(
        event,
        f"chat_id = {chat_id}\n"
        f"state = {state}\n"
        f"class = {cf}\n"
        f"user = {user['name'] if user else 'NO_USER'}",
    )


@dp.message_created()
async def handle_text(event: MessageCreated):
    chat_id = get_chat_id(event)
    try:
        text = (event.message.body.text or "").strip()
    except AttributeError:
        return
    state = user_states.get(chat_id, {})
    logging.info(f"[TEXT] chat={chat_id} text={text!r} state={state}")

    # ---- ВВОД КОДА ----
    if state.get("state") == "waiting_code":
        cf = state.get("class_file")
        expected_code = state.get("code")
        user = get_user_by_code(cf, expected_code) if cf else None
        if user and text == expected_code:
            users = load_class_data(cf)
            for u in users:
                if u['id'] == expected_code:
                    u['chat_id'] = chat_id
                    break
            save_class_data(cf, users)
            del user_states[chat_id]
            kb = kb_student_menu() if user['role'] == 'student' else kb_teacher_menu()
            await reply(event, f"✅ {user['name']}, добро пожаловать!\nКласс: {class_display_name(cf)}", kb)
        else:
            await reply(event, "❌ Неверный код.\n\nПопробуйте ещё раз — введите 4-значный код из списка, который вам выдали.")
        return

    # ---- ВВОД ИМЕНИ НОВОГО УЧЕНИКА ----
    if state.get("state") == "waiting_new_student_name":
        cf = state.get("class_file")
        user, _ = find_user_by_chat_id(chat_id)
        if not user or user.get('role') != 'teacher' or not cf:
            return
        name = text.strip()
        if len(name) < 2:
            return await reply(event, "❌ Имя слишком короткое. Введите имя и фамилию (например, «Иванов Иван»).")
        if len(name) > 60:
            return await reply(event, "❌ Имя слишком длинное. Максимум 60 символов.")
        users = load_class_data(cf)
        if any(u['name'].strip().lower() == name.lower() for u in users):
            return await reply(event, f"❌ Ученик с именем «{name}» уже есть в классе.")
        code = generate_unique_code(cf)
        users.append({
            "id": code,
            "name": name,
            "balance": 0,
            "role": "student",
            "chat_id": None,
            "purchases": [],
        })
        save_class_data(cf, users)
        user_states.pop(chat_id, None)
        await reply(
            event,
            f"✅ **Ученик добавлен**\n\n"
            f"👤 {name}\n"
            f"🔑 Код для входа: **{code}**\n\n"
            f"Передайте ученику этот код — он введёт его при первом входе в бота.",
            kb_manage_students(),
        )
        return

    # ---- ПЕРЕВОД УЧЕНИКУ ----
    if state.get("state") == "waiting_transfer_amount":
        cf = state.get("class_file")
        user, _ = find_user_by_chat_id(chat_id)
        if not user or not cf:
            return
        try:
            amount = int(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return await reply(event, "❌ Введите целое число — сколько баллов перевести (например, 10).")
        tid = state.get("target_id")
        target = get_user_by_code(cf, tid)
        mx = int(user['balance'] * 0.3)
        if amount > mx:
            return await reply(event, f"❌ Слишком много. Максимум {mx} б. (30% от вашего баланса).")
        if amount > user['balance']:
            return await reply(event, "❌ Недостаточно баллов на балансе.")
        users = load_class_data(cf)
        for u in users:
            if u['id'] == user['id']:
                u['balance'] -= amount
            elif u['id'] == tid:
                u['balance'] += amount
        save_class_data(cf, users)
        del user_states[chat_id]
        await reply(event, f"✅ Переведено {amount} б. → {target['name']}\n\nОстаток: {user['balance'] - amount} б.", kb_student_menu())
        return

    # ---- ПЕРЕВОД В КОТЁЛ ----
    if state.get("state") == "waiting_pot_amount":
        cf = state.get("class_file")
        user, _ = find_user_by_chat_id(chat_id)
        if not user or not cf:
            return
        try:
            amount = int(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return await reply(event, "❌ Введите целое число — сколько баллов перевести (например, 10).")
        mx = int(user['balance'] * 0.3)
        if amount > mx:
            return await reply(event, f"❌ Слишком много. Максимум {mx} б. (30% от вашего баланса).")
        if amount > user['balance']:
            return await reply(event, "❌ Недостаточно баллов на балансе.")
        users = load_class_data(cf)
        for u in users:
            if u['id'] == user['id']:
                u['balance'] -= amount
                break
        save_class_data(cf, users)
        pot = load_pot(cf)
        pot['current'] = min(pot['current'] + amount, pot['goal'])
        save_pot(cf, pot)
        del user_states[chat_id]
        await reply(
            event,
            f"✅ Переведено {amount} б. в общий котёл.\n\n"
            f"Ваш остаток: {user['balance'] - amount} б.\n"
            f"Котёл: {pot['current']} / {pot['goal']} б.",
            kb_student_menu(),
        )
        return

    # ---- ПОПОЛНЕНИЕ КОТЛА УЧИТЕЛЕМ ----
    if state.get("state") == "waiting_teacher_pot_amount":
        cf_sel = state.get("class_file")
        user, _ = find_user_by_chat_id(chat_id)
        logging.info(
            f"[TEACHER_POT] chat={chat_id} text={text!r} "
            f"user={user['name'] if user else None} role={user.get('role') if user else None} cf={cf_sel}"
        )
        if not user or not cf_sel:
            return
        if user.get('role') != 'teacher':
            return
        try:
            amount = int(text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            return await reply(event, "❌ Введите целое положительное число — на сколько баллов пополнить котёл (например, 10).")

        pot = load_pot(cf_sel)
        pot['current'] = min(pot['current'] + amount, pot['goal'])
        save_pot(cf_sel, pot)
        user_states.pop(chat_id, None)

        await reply(
            event,
            f"✅ Котёл успешно пополнен на **{amount} б.**\n\n"
            f"🏺 Текущее состояние котла: **{pot['current']} / {pot['goal']} б.**\n"
            f"Осталось собрать: {max(0, pot['goal'] - pot['current'])} б.\n\n"
            f"Цель: {pot['description']}",
            kb_teacher_menu(),
        )
        return


# ================= ЗАПУСК =================
async def main():
    init_data()
    logging.info(f"Бот СпектрБалл запущен! Классов: {len(list_classes())} → {list_classes()}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
