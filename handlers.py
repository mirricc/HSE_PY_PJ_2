import asyncio
import os
import requests
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any, List
from io import BytesIO

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from aiogram import Bot, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from states import ProfileForm, WaterForm, FoodForm, WorkoutForm

from config import OPENWEATHER_API_KEY
router = Router()

users: Dict[int, Dict[str, Any]] = {}



LOW_CAL_FOODS = [
    {"name": "банан", "calories": 89, "portion": 100, "emoji": "🍌"},
    {"name": "яблоко", "calories": 52, "portion": 100, "emoji": "🍎"},
    {"name": "огурец", "calories": 15, "portion": 100, "emoji": "🥒"},
    {"name": "морковь", "calories": 41, "portion": 100, "emoji": "🥕"},
    {"name": "йогурт натуральный", "calories": 59, "portion": 100, "emoji": "🍶"},
    {"name": "яйцо варёное", "calories": 155, "portion": 50, "emoji": "🥚"},  # 1 яйцо ~50г
    {"name": "творог 5%", "calories": 120, "portion": 100, "emoji": "🧀"},
]

BURN_WORKOUTS = [
    {"name": "ходьба", "cal_per_min": 4, "emoji": "🚶", "intensity": "лёгкая"},
    {"name": "бег трусцой", "cal_per_min": 8, "emoji": "🏃", "intensity": "средняя"},
    {"name": "велосипед", "cal_per_min": 8, "emoji": "🚴", "intensity": "средняя"},
    {"name": "прыжки на скакалке", "cal_per_min": 12, "emoji": "🤸", "intensity": "интенсивная"},
    {"name": "танцы", "cal_per_min": 6, "emoji": "💃", "intensity": "средняя"},
]


def ensure_user_exists(user_id: int):
    """Гарантирует, что пользователь существует в словаре users с историей"""
    if user_id not in users:
        users[user_id] = {
            'weight': None, 'height': None, 'age': None, 'gender': None,
            'activity': None, 'city': None, 'water_goal': 2000, 'calorie_goal': 2000,
            'logged_water': 0, 'logged_calories': 0, 'burned_calories': 0,
            'last_update': datetime.now(),
            'pending_food': None,
            'history': {}
        }


def is_profile_complete(user_id: int) -> bool:
    """Проверяет, полностью ли настроен профиль пользователя"""
    user = users.get(user_id)
    if not user:
        return False
    return all([
        user['weight'] is not None,
        user['height'] is not None,
        user['age'] is not None,
        user['gender'] is not None,
        user['activity'] is not None,
        user['city'] is not None
    ])


def reset_daily_data(user_id: int):
    """Сбрасывает данные за день при первом обращении после полуночи"""
    user = users.get(user_id)
    if not user:
        return
    
    now = datetime.now()
    last_update = user.get('last_update', now)
    
    if (now - last_update).days >= 1:
        user.update({
            'logged_water': 0,
            'logged_calories': 0,
            'burned_calories': 0,
            'last_update': now
        })


def save_daily_stats(user_id: int):
    """Сохраняет текущие данные пользователя в историю за сегодня"""
    user = users.get(user_id)
    if not user:
        return
    
    today = datetime.now().date().isoformat()
    
    if today not in user['history']:
        user['history'][today] = {
            'water': 0,
            'calories_consumed': 0,
            'calories_burned': 0,
            'water_goal': user['water_goal'],
            'calorie_goal': user['calorie_goal']
        }
    
    user['history'][today].update({
        'water': user['logged_water'],
        'calories_consumed': user['logged_calories'],
        'calories_burned': user['burned_calories'],
        'water_goal': user['water_goal'],
        'calorie_goal': user['calorie_goal']
    })


def get_last_n_days_data(user_id: int, n: int = 7) -> tuple:
    """Возвращает данные за последние N дней для построения графиков"""
    user = users.get(user_id)
    if not user or not user['history']:
        return [], [], [], [], [], []
    
    sorted_dates = sorted(user['history'].keys())[-n:]
    
    dates = []
    water_values = []
    water_goals = []
    calories_consumed = []
    calories_burned = []
    calorie_goals = []
    
    for d in sorted_dates:
        record = user['history'][d]
        dates.append(d[5:])
        water_values.append(record['water'])
        water_goals.append(record['water_goal'])
        calories_consumed.append(record['calories_consumed'])
        calories_burned.append(record['calories_burned'])
        calorie_goals.append(record['calorie_goal'])
    
    return dates, water_values, water_goals, calories_consumed, calories_burned, calorie_goals


def create_progress_charts(user_id: int) -> BytesIO | None:
    """Создаёт графики прогресса и возвращает изображение в буфере"""
    dates, water_vals, water_goals, cal_cons, cal_burn, cal_goals = get_last_n_days_data(user_id, 7)
    
    if not dates:
        return None
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    fig.suptitle('Прогресс за последние 7 дней', fontsize=16, fontweight='bold', color='#2C3E50')
    
    x = range(len(dates))
    ax1.bar(x, water_vals, color='#3498DB', alpha=0.85, label='Выпито', edgecolor='white', linewidth=1.5)
    ax1.plot(x, water_goals, 'r--', marker='o', linewidth=2.5, label='Норма', markersize=8, color='#E74C3C')
    
    for i, (val, goal) in enumerate(zip(water_vals, water_goals)):
        ax1.text(i, val + max(water_goals) * 0.03, f'{int(val)} мл', 
                ha='center', va='bottom', fontsize=9, fontweight='bold', color='#2C3E50')
        if val >= goal:
            ax1.text(i, goal * 0.3, ha='center', va='center', 
                    fontsize=16, color='green', fontweight='bold')
    
    ax1.set_xticks(x)
    ax1.set_xticklabels(dates, rotation=45, ha='right', fontsize=10)
    ax1.set_ylabel('Вода (мл)', fontsize=12, fontweight='bold', color='#2C3E50')
    ax1.set_title('Потребление воды', fontsize=14, pad=12, color='#2C3E50')
    ax1.legend(loc='upper left', frameon=True, shadow=True)
    ax1.grid(axis='y', alpha=0.3, linestyle='--')
    ax1.set_ylim(0, max(max(water_goals) * 1.25, max(water_vals) * 1.25) if water_vals else 2500)
    ax1.set_facecolor('#F8F9FA')
    
    width = 0.35
    ax2.bar([i - width/2 for i in x], cal_cons, width, 
           color='#E67E22', alpha=0.85, label='Потреблено', edgecolor='white', linewidth=1.5)
    ax2.bar([i + width/2 for i in x], cal_burn, width, 
           color='#1ABC9C', alpha=0.85, label='Сожжено', edgecolor='white', linewidth=1.5)
    ax2.plot(x, cal_goals, 'r--', marker='o', linewidth=2.5, label='Норма', markersize=8, color='#E74C3C')
    
    for i, (cons, burn, goal) in enumerate(zip(cal_cons, cal_burn, cal_goals)):
        net = cons - burn
        color = 'green' if net <= goal else '#E67E22'
        ax2.text(i, max(cons, burn) + max(cal_goals) * 0.05, 
                f'{int(net)}', ha='center', va='bottom', 
                fontsize=10, fontweight='bold', color=color)
    
    ax2.set_xticks(x)
    ax2.set_xticklabels(dates, rotation=45, ha='right', fontsize=10)
    ax2.set_ylabel('Калории (ккал)', fontsize=12, fontweight='bold', color='#2C3E50')
    ax2.set_title('Баланс калорий (потреблено - сожжено)', fontsize=14, pad=12, color='#2C3E50')
    ax2.legend(loc='upper left', frameon=True, shadow=True)
    ax2.grid(axis='y', alpha=0.3, linestyle='--')
    ax2.set_ylim(0, max(max(cal_goals) * 1.35, max(cal_cons + cal_burn) * 1.35) if (cal_cons or cal_burn) else 3000)
    ax2.set_facecolor('#F8F9FA')
    
    fig.patch.set_facecolor('white')
    plt.tight_layout()
    
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)
    
    return buf

def get_food_recommendations(user_id: int) -> List[Dict[str, Any]]:
    """Возвращает рекомендации низкокалорийных продуктов при недоборе калорий"""
    user = users.get(user_id)
    if not user or not user['calorie_goal']:
        return []
    
    net_calories = user['logged_calories'] - user['burned_calories']
    deficit = user['calorie_goal'] - net_calories
    
    if deficit < user['calorie_goal'] * 0.15:
        return []
    
    recommendations = []
    for food in LOW_CAL_FOODS:
        portion_calories = food['calories'] * food['portion'] / 100
        portions_needed = min(3, max(1, int((deficit * 0.3) / portion_calories)))
        total_calories = portion_calories * portions_needed
        
        recommendations.append({
            'food': food,
            'portions': portions_needed,
            'total_calories': total_calories,
            'deficit_covered_pct': min(100, int(total_calories / deficit * 100))
        })
    
    recommendations.sort(key=lambda x: x['deficit_covered_pct'], reverse=True)
    return recommendations[:3]


def get_workout_recommendations(user_id: int) -> List[Dict[str, Any]]:
    """Возвращает рекомендации тренировок при превышении калорий"""
    user = users.get(user_id)
    if not user or not user['calorie_goal']:
        return []
    
    net_calories = user['logged_calories'] - user['burned_calories']
    surplus = net_calories - user['calorie_goal']
    
    if surplus < user['calorie_goal'] * 0.2:
        return []
    
    recommendations = []
    for workout in BURN_WORKOUTS:
        minutes_needed = min(60, max(10, int((surplus * 0.4) / workout['cal_per_min'])))
        calories_burned = workout['cal_per_min'] * minutes_needed
        
        recommendations.append({
            'workout': workout,
            'minutes': minutes_needed,
            'calories_burned': calories_burned,
            'surplus_reduced_pct': min(100, int(calories_burned / surplus * 100))
        })
    
    recommendations.sort(key=lambda x: x['surplus_reduced_pct'], reverse=True)
    return recommendations[:3]  


def format_recommendations(user_id: int) -> str:
    """Форматирует рекомендации в красивый текст"""
    user = users.get(user_id)
    if not user:
        return ""
    
    net_calories = user['logged_calories'] - user['burned_calories']
    deficit = user['calorie_goal'] - net_calories
    surplus = net_calories - user['calorie_goal']
    
    parts = []
    
    if deficit > user['calorie_goal'] * 0.15:
        parts.append(f"\n🍽️ <b>Вам не хватает {deficit:.0f} ккал до нормы!</b>")
        recs = get_food_recommendations(user_id)
        for i, rec in enumerate(recs, 1):
            food = rec['food']
            portions = rec['portions']
            total_cals = rec['total_calories']
            pct = rec['deficit_covered_pct']
            portion_desc = f"{portions}×{food['portion']}г" if portions > 1 else f"{food['portion']}г"
            parts.append(
                f"{i}. {food['emoji']} {food['name'].capitalize()} ({portion_desc}) — "
                f"{total_cals:.0f} ккал (+{pct}% к норме)"
            )
    
    if surplus > user['calorie_goal'] * 0.2:
        parts.append(f"\n🔥 <b>Вы превысили норму на {surplus:.0f} ккал!</b>")
        recs = get_workout_recommendations(user_id)
        for i, rec in enumerate(recs, 1):
            w = rec['workout']
            minutes = rec['minutes']
            cals = rec['calories_burned']
            pct = rec['surplus_reduced_pct']
            parts.append(
                f"{i}. {w['emoji']} {w['name'].capitalize()} {w['intensity']} "
                f"({minutes} мин) — сожжёт {cals:.0f} ккал (-{pct}% от излишка)"
            )
    
    return "\n".join(parts) if parts else ""


def get_recommendation_buttons(user_id: int) -> InlineKeyboardMarkup | None:
    """Создаёт кнопки для быстрого логирования рекомендованных действий"""
    user = users.get(user_id)
    if not user:
        return None
    
    net_calories = user['logged_calories'] - user['burned_calories']
    deficit = user['calorie_goal'] - net_calories
    surplus = net_calories - user['calorie_goal']
    
    buttons = []
    
    if deficit > user['calorie_goal'] * 0.15:
        recs = get_food_recommendations(user_id)
        if recs:
            top = recs[0]
            food = top['food']
            portions = top['portions']
            total_grams = food['portion'] * portions
            buttons.append([
                InlineKeyboardButton(
                    text=f"🍌 Съесть {food['name']} ({total_grams}г)",
                    callback_data=f"quick_log_food:{food['name']}:{total_grams}"
                )
            ])
    
    if surplus > user['calorie_goal'] * 0.2:
        recs = get_workout_recommendations(user_id)
        if recs:
            top = recs[0]
            w = top['workout']
            minutes = top['minutes']
            buttons.append([
                InlineKeyboardButton(
                    text=f"🚶 Погулять {minutes} мин",
                    callback_data=f"quick_log_workout:{w['name']}:{minutes}"
                )
            ])
    
    if buttons:
        buttons.append([
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close_recommendations")
        ])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    return None


@router.callback_query(lambda c: c.data.startswith("quick_log_food:"))
async def quick_log_food(callback: CallbackQuery, state: FSMContext):
    _, product, grams = callback.data.split(":")
    user_id = callback.from_user.id
    
    ensure_user_exists(user_id)
    reset_daily_data(user_id)
    
    food = search_food(product)
    if food:
        calories = food['calories'] * float(grams) / 100
        users[user_id]['logged_calories'] += calories
        save_daily_stats(user_id)
        
        await callback.answer()
        await callback.message.edit_text(
            f"✅ Быстро записано: {grams}г {food['name']} — {calories:.1f} ккал\n"
            f"Всего сегодня: {users[user_id]['logged_calories']:.1f} ккал"
        )
    else:
        await callback.answer("❌ Продукт не найден", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("quick_log_workout:"))
async def quick_log_workout(callback: CallbackQuery, state: FSMContext):
    _, workout_type, minutes = callback.data.split(":")
    user_id = callback.from_user.id
    
    ensure_user_exists(user_id)
    reset_daily_data(user_id)
    
    # Логируем тренировку
    cal_per_min = WORKOUT_CALORIES.get(workout_type.lower(), 4)
    burned = int(cal_per_min * int(minutes))
    users[user_id]['burned_calories'] += burned
    save_daily_stats(user_id)
    
    await callback.answer()
    await callback.message.edit_text(
        f"✅ Быстро записано: {workout_type.capitalize()} {minutes} мин — {burned} ккал сожжено"
    )


@router.callback_query(lambda c: c.data == "show_progress")
async def show_progress_from_callback(callback: CallbackQuery):
    await callback.answer()
    await check_progress(callback.message)


@router.callback_query(lambda c: c.data == "close_recommendations")
async def close_recommendations(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()

def get_cancel_help_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_operation"),
            InlineKeyboardButton(text="ℹ️ Помощь", callback_data="show_help")
        ]
    ])


FOOD_FALLBACK = {
    "банан": 89, "яблоко": 52, "апельсин": 47, "хлеб": 265, "рис": 130,
    "курица": 165, "говядина": 250, "рыба": 205, "яйцо": 155, "молоко": 42,
    "кефир": 40, "творог": 120, "картошка": 77, "макароны": 158,
    "шоколад": 546, "вода": 0, "кофе": 2, "чай": 1, "кола": 42, "пиво": 43
}

WORKOUT_CALORIES = {
    "бег": 10, "ходьба": 4, "велосипед": 8, "плавание": 9, "йога": 5,
    "силовая": 8, "танцы": 6, "футбол": 10, "баскетбол": 9, "теннис": 8
}


def get_food_info(product_name: str) -> Optional[Dict[str, Any]]:
    try:
        encoded_name = urllib.parse.quote(product_name.strip())
        url = (
            f"https://world.openfoodfacts.org/cgi/search.pl?"
            f"action=process&"
            f"search_terms={encoded_name}&"
            f"json=1&"
            f"page_size=3"
        )
        response = requests.get(url, timeout=8)
        if response.status_code != 200:
            return None
        
        data = response.json()
        products = data.get('products', [])
        
        for product in products:
            # Получаем название на русском или английском
            name = (
                product.get('product_name_ru') or 
                product.get('product_name') or 
                'Неизвестный продукт'
            ).strip()
            
            nutriments = product.get('nutriments', {})
            calories = (
                nutriments.get('energy-kcal_100g') or
                nutriments.get('energy_100g', 0) / 4.184 or 
                0
            )
            
            if calories > 0 and name and name.lower() != 'unknown':
                serving_size = product.get('serving_size', '100г')
                
                return {
                    'name': name.capitalize(),
                    'calories': round(float(calories), 1),
                    'serving_size': serving_size
                }
        
        return None
    except Exception:
        return None


def search_food(product_name: str) -> Optional[Dict[str, Any]]:
    result = get_food_info(product_name)
    if result:
        return result
    
    product_lower = product_name.strip().lower()
    if product_lower in FOOD_FALLBACK:
        return {
            'name': product_lower.capitalize(),
            'calories': FOOD_FALLBACK[product_lower]
        }
    
    for key, calories in FOOD_FALLBACK.items():
        if product_lower in key or key in product_lower:
            return {
                'name': key.capitalize(),
                'calories': calories
            }
    return None


async def get_weather(city: str) -> Dict[str, Any]:
    try:
        encoded_city = urllib.parse.quote(city)
        url = f"http://api.openweathermap.org/data/2.5/weather?q={encoded_city}&appid={OPENWEATHER_API_KEY}&units=metric"
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, lambda: requests.get(url, timeout=8))
        
        if response.status_code == 200:
            data = response.json()
            return {'success': True, 'temp': data['main']['temp']}
        return {'success': False, 'error': f"Город '{city}' не найден"}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def calculate_water_goal(weight: float, activity: int, temp: float) -> int:
    return int(weight * 30 + (activity // 30) * 500 + (750 if temp > 25 else 0))


def calculate_calorie_goal(weight: float, height: float, age: int, gender: str, activity: int) -> int:
    bmr = 10 * weight + 6.25 * height - 5 * age + (5 if gender.lower() in ['м', 'муж', 'male', 'm'] else -161)
    factor = 1.2 if activity < 30 else 1.375 if activity < 60 else 1.55 if activity < 90 else 1.725
    return int(bmr * factor)


@router.callback_query(lambda c: c.data == "cancel_operation")
async def callback_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("❌ Операция отменена")
    try:
        await callback.message.edit_text("❌ Операция отменена.", reply_markup=None)
    except TelegramBadRequest:
        await callback.message.answer("❌ Операция отменена.")


@router.callback_query(lambda c: c.data == "show_help")
async def callback_help(callback: CallbackQuery):
    help_text = (
        "📖 Справка:\n\n"
        "• /set_profile — настроить профиль\n"
        "• /view_profile — посмотреть профиль\n"
        "• /log_water — записать воду\n"
        "• /log_food — записать еду\n"
        "• /log_workout — записать тренировку\n"
        "• /check_progress — прогресс за день\n"
        "• /show_stats — 📈 графики за неделю\n"
        "• /recommend — получить персональные рекомендации"
    )
    await callback.answer()
    try:
        await callback.message.edit_text(help_text, reply_markup=get_cancel_help_buttons())
    except TelegramBadRequest:
        await callback.message.answer(help_text, reply_markup=get_cancel_help_buttons())


@router.callback_query(lambda c: c.data == "set_profile")
async def callback_set_profile(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_profile_form(callback.message, state)


@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    ensure_user_exists(message.from_user.id)
    await message.answer(
        "👋 Привет! Я бот для отслеживания воды и калорий.\n"
        "Сначала настройте профиль командой /set_profile",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔧 Настроить профиль", callback_data="set_profile")]
        ])
    )


@router.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных операций для отмены.")
        return
    
    await state.clear()
    await message.answer("❌ Операция отменена.", reply_markup=None)


@router.message(Command("set_profile"))
async def start_profile_form(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    await state.set_state(ProfileForm.weight)
    await message.answer(
        "👤 Настройка профиля\n\nВведите ваш вес (в кг):",
        reply_markup=get_cancel_help_buttons()
    )


@router.message(ProfileForm.weight)
async def process_weight(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    try:
        weight = float(message.text.replace(',', '.'))
        if not 30 <= weight <= 300:
            raise ValueError
        await state.update_data(weight=weight)
        await message.answer(
            f"✅ Вес: {weight} кг\nВведите ваш рост (в см):",
            reply_markup=get_cancel_help_buttons()
        )
        await state.set_state(ProfileForm.height)
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введите корректный вес в кг (например, 75):",
            reply_markup=get_cancel_help_buttons()
        )


@router.message(ProfileForm.height)
async def process_height(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    try:
        height = float(message.text.replace(',', '.'))
        if not 100 <= height <= 250:
            raise ValueError
        await state.update_data(height=height)
        await message.answer(
            f"✅ Рост: {height} см\nВведите ваш возраст:",
            reply_markup=get_cancel_help_buttons()
        )
        await state.set_state(ProfileForm.age)
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введите корректный рост в см (например, 175):",
            reply_markup=get_cancel_help_buttons()
        )


@router.message(ProfileForm.age)
async def process_age(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    try:
        age = int(message.text)
        if not 10 <= age <= 120:
            raise ValueError
        await state.update_data(age=age)
        await message.answer(
            f"✅ Возраст: {age} лет\nВведите ваш пол (м/ж):",
            reply_markup=get_cancel_help_buttons()
        )
        await state.set_state(ProfileForm.gender)
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введите корректный возраст (например, 25):",
            reply_markup=get_cancel_help_buttons()
        )


@router.message(ProfileForm.gender)
async def process_gender(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    gender = message.text.strip().lower()
    if gender not in ['м', 'ж', 'мужской', 'женский', 'муж', 'жен', 'male', 'female', 'm', 'f']:
        await message.answer(
            "❌ Введите пол (м/ж):",
            reply_markup=get_cancel_help_buttons()
        )
        return
    await state.update_data(gender=gender)
    await message.answer(
        f"✅ Пол: {gender}\nСколько минут активности у вас в день?",
        reply_markup=get_cancel_help_buttons()
    )
    await state.set_state(ProfileForm.activity)


@router.message(ProfileForm.activity)
async def process_activity(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    try:
        activity = int(message.text)
        if not 0 <= activity <= 300:
            raise ValueError
        await state.update_data(activity=activity)
        await message.answer(
            f"✅ Активность: {activity} мин/день\nВ каком городе вы находитесь?",
            reply_markup=get_cancel_help_buttons()
        )
        await state.set_state(ProfileForm.city)
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введите количество минут активности (например, 45):",
            reply_markup=get_cancel_help_buttons()
        )


@router.message(ProfileForm.city)
async def process_city(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    city = message.text.strip()
    await state.update_data(city=city)
    
    data = await state.get_data()
    user_id = message.from_user.id
    
    weather = await get_weather(city)
    temperature = weather['temp'] if weather['success'] else 20.0
    
    if not weather['success']:
        await message.answer(f"⚠️ {weather['error']}\nТемпература установлена 20°C по умолчанию.")
    
    water_goal = calculate_water_goal(data['weight'], data['activity'], temperature)
    calorie_goal = calculate_calorie_goal(
        data['weight'], data['height'], data['age'], data['gender'], data['activity']
    )
    
    users[user_id].update({
        'weight': data['weight'],
        'height': data['height'],
        'age': data['age'],
        'gender': data['gender'],
        'activity': data['activity'],
        'city': city,
        'water_goal': water_goal,
        'calorie_goal': calorie_goal,
        'last_update': datetime.now()
    })
    
    await state.clear()
    
    await message.answer(
        f"🎉 Профиль настроен!\n\n"
        f"📍 Город: {city} ({temperature:.1f}°C)\n"
        f"💧 Норма воды: {water_goal} мл\n"
        f"🔥 Норма калорий: {calorie_goal} ккал\n\n"
        f"Теперь вы можете:\n"
        f"• /log_water — записать воду\n"
        f"• /log_food — записать еду\n"
        f"• /log_workout — записать тренировку\n"
        f"• /check_progress — прогресс за день\n"
        f"• /show_stats — 📈 графики за неделю\n"
        f"• /recommend — 💡 персональные рекомендации"
    )


@router.message(Command("log_water"))
async def start_log_water(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    reset_daily_data(message.from_user.id)
    
    if not is_profile_complete(message.from_user.id):
        await message.answer(
            "⚠️ Сначала настройте профиль командой /set_profile",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настроить профиль", callback_data="set_profile")]
            ])
        )
        return
    
    await state.set_state(WaterForm.amount)
    await message.answer(
        "💧 Сколько миллилитров воды вы выпили?",
        reply_markup=get_cancel_help_buttons()
    )


@router.message(WaterForm.amount)
async def process_water_amount(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    try:
        ml = int(message.text)
        if ml <= 0:
            raise ValueError
        
        user_id = message.from_user.id
        users[user_id]['logged_water'] += ml
        remaining = users[user_id]['water_goal'] - users[user_id]['logged_water']
        
        save_daily_stats(user_id)
        await state.clear()
        
        response = f"✅ Записано {ml} мл воды.\n"
        if remaining <= 0:
            response += f"🎯 Норма воды выполнена! (+{abs(remaining)} мл сверх нормы)"
        else:
            response += f"💧 Осталось выпить: {remaining} мл из {users[user_id]['water_goal']} мл"
        
        # Добавляем рекомендации по калориям после логирования воды
        rec_text = format_recommendations(user_id)
        if rec_text:
            response += f"\n\n{rec_text}"
            await message.answer(response, parse_mode="HTML", reply_markup=get_recommendation_buttons(user_id))
        else:
            await message.answer(response)
    
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введите корректное количество в мл (целое число, например: 300):",
            reply_markup=get_cancel_help_buttons()
        )


@router.message(Command("log_food"))
async def start_log_food(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    reset_daily_data(message.from_user.id)
    
    if not is_profile_complete(message.from_user.id):
        await message.answer(
            "⚠️ Сначала настройте профиль командой /set_profile",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настроить профиль", callback_data="set_profile")]
            ])
        )
        return
    
    await state.set_state(FoodForm.product)
    await message.answer(
        "🍎 Какой продукт вы съели?",
        reply_markup=get_cancel_help_buttons()
    )


@router.message(FoodForm.product)
async def process_food_product(message: Message, state: FSMContext, bot: Bot):
    ensure_user_exists(message.from_user.id)
    product = message.text.strip()
    
    if not product:
        await message.answer(
            "❌ Введите название продукта:",
            reply_markup=get_cancel_help_buttons()
        )
        return
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    food = search_food(product)
    
    if not food:
        suggestions = [p for p in FOOD_FALLBACK if product.lower() in p or p in product.lower()][:3]
        if suggestions:
            await message.answer(
                f"❌ Продукт '{product}' не найден.\n"
                f"Возможно, вы имели в виду: {', '.join(suggestions)}\n\n"
                "Введите название продукта:",
                reply_markup=get_cancel_help_buttons()
            )
        else:
            await message.answer(
                "❌ Продукт не найден. Попробуйте упростить название (например, 'банан').\n\n"
                "Введите название продукта:",
                reply_markup=get_cancel_help_buttons()
            )
        return
    
    await state.update_data(pending_food=food)
    await state.set_state(FoodForm.grams)
    await message.answer(
        f"✅ Найден продукт: {food['name']}\n"
        f"Калорийность: {food['calories']} ккал на 100г\n"
        f"Сколько грамм вы съели?",
        reply_markup=get_cancel_help_buttons()
    )


@router.message(FoodForm.grams)
async def process_food_grams(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    data = await state.get_data()
    food = data.get('pending_food')
    
    if not food:
        await state.clear()
        await message.answer("❌ Ошибка. Начните заново: /log_food")
        return
    
    try:
        grams = float(message.text.replace(',', '.'))
        if not 1 <= grams <= 5000:
            raise ValueError
        
        calories = food['calories'] * grams / 100
        user_id = message.from_user.id
        users[user_id]['logged_calories'] += calories
        
        save_daily_stats(user_id)
        await state.clear()
        
        response = f"✅ Записано: {grams:.0f}г {food['name']} — {calories:.1f} ккал\n"
        response += f"Всего сегодня: {users[user_id]['logged_calories']:.1f} ккал"
        
        # Добавляем рекомендации после логирования еды
        rec_text = format_recommendations(user_id)
        if rec_text:
            response += f"\n\n{rec_text}"
            await message.answer(response, parse_mode="HTML", reply_markup=get_recommendation_buttons(user_id))
        else:
            await message.answer(response)
    
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введите корректное количество в граммах (например, 150):",
            reply_markup=get_cancel_help_buttons()
        )


@router.message(Command("log_workout"))
async def start_log_workout(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    reset_daily_data(message.from_user.id)
    
    if not is_profile_complete(message.from_user.id):
        await message.answer(
            "⚠️ Сначала настройте профиль командой /set_profile",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настроить профиль", callback_data="set_profile")]
            ])
        )
        return
    
    await state.set_state(WorkoutForm.type)
    await message.answer(
        "💪 Какой тип тренировки вы выполнили?\n"
        f"Доступные типы: {', '.join(WORKOUT_CALORIES.keys())}",
        reply_markup=get_cancel_help_buttons()
    )


@router.message(WorkoutForm.type)
async def process_workout_type(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    workout_type = message.text.strip().lower()
    
    matched_type = None
    for key in WORKOUT_CALORIES.keys():
        if workout_type == key or workout_type in key or key in workout_type:
            matched_type = key
            break
    
    if not matched_type:
        suggestions = [t for t in WORKOUT_CALORIES.keys() if workout_type in t or t in workout_type][:3]
        if suggestions:
            await message.answer(
                f"❌ Тип '{workout_type}' не найден.\n"
                f"Возможно, вы имели в виду: {', '.join(suggestions)}\n\n"
                "Введите тип тренировки:",
                reply_markup=get_cancel_help_buttons()
            )
        else:
            await message.answer(
                f"❌ Неизвестный тип тренировки.\n"
                f"Доступные типы: {', '.join(WORKOUT_CALORIES.keys())}\n\n"
                "Введите тип тренировки:",
                reply_markup=get_cancel_help_buttons()
            )
        return
    
    await state.update_data(workout_type=matched_type)
    await state.set_state(WorkoutForm.duration)
    await message.answer(
        f"✅ Тип: {matched_type.capitalize()}\nСколько минут длилась тренировка?",
        reply_markup=get_cancel_help_buttons()
    )


@router.message(WorkoutForm.duration)
async def process_workout_duration(message: Message, state: FSMContext):
    ensure_user_exists(message.from_user.id)
    data = await state.get_data()
    workout_type = data.get('workout_type')
    
    if not workout_type:
        await state.clear()
        await message.answer("❌ Ошибка. Начните заново: /log_workout")
        return
    
    try:
        duration = int(message.text)
        if duration <= 0:
            raise ValueError
        
        cal_per_min = WORKOUT_CALORIES[workout_type]
        burned = int(cal_per_min * duration)
        water_needed = (duration // 30) * 200
        
        user_id = message.from_user.id
        users[user_id]['burned_calories'] += burned
        
        save_daily_stats(user_id)
        await state.clear()
        
        response = (
            f"💪 Тренировка записана:\n"
            f"Тип: {workout_type.capitalize()}\n"
            f"Длительность: {duration} мин\n"
            f"Сожжено: {burned} ккал"
        )
        if water_needed > 0:
            response += f"\n💧 Рекомендуется доп. выпить: {water_needed} мл воды"
        
        # Добавляем рекомендации после логирования тренировки
        rec_text = format_recommendations(user_id)
        if rec_text:
            response += f"\n\n{rec_text}"
            await message.answer(response, parse_mode="HTML", reply_markup=get_recommendation_buttons(user_id))
        else:
            await message.answer(response)
    
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Введите корректную длительность в минутах (целое число, например: 30):",
            reply_markup=get_cancel_help_buttons()
        )


@router.message(Command("view_profile"))
async def view_profile(message: Message):
    ensure_user_exists(message.from_user.id)
    
    if not is_profile_complete(message.from_user.id):
        await message.answer(
            "⚠️ Профиль ещё не настроен.\n"
            "Настройте его командой /set_profile",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настроить профиль", callback_data="set_profile")]
            ])
        )
        return
    
    user = users[message.from_user.id]
    profile_info = "👤 Ваш профиль:\n\n"
    profile_info += f"Вес: {user['weight']} кг\n"
    profile_info += f"Рост: {user['height']} см\n"
    profile_info += f"Возраст: {user['age']} лет\n"
    profile_info += f"Пол: {user['gender'].upper()}\n"
    profile_info += f"Активность: {user['activity']} мин/день\n"
    profile_info += f"Город: {user['city']}\n\n"
    profile_info += f"💧 Норма воды: {user['water_goal']} мл/день\n"
    profile_info += f"🔥 Норма калорий: {user['calorie_goal']} ккал/день"
    
    await message.answer(profile_info)


@router.message(Command("check_progress"))
async def check_progress(message: Message):
    ensure_user_exists(message.from_user.id)
    reset_daily_data(message.from_user.id)
    
    if not is_profile_complete(message.from_user.id):
        await message.answer(
            "⚠️ Сначала настройте профиль командой /set_profile",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настроить профиль", callback_data="set_profile")]
            ])
        )
        return
    
    u = users[message.from_user.id]
    net_calories = u['logged_calories'] - u['burned_calories']
    
    water_pct = min(100, int(u['logged_water'] / u['water_goal'] * 100))
    water_bar = '█' * (water_pct // 10) + '░' * (10 - water_pct // 10)
    
    calorie_pct = min(100, int(net_calories / u['calorie_goal'] * 100)) if u['calorie_goal'] > 0 else 0
    calorie_bar = '█' * (calorie_pct // 10) + '░' * (10 - calorie_pct // 10)
    
    response = "📊 Ежедневный прогресс:\n\n"
    response += f"💧 Вода:\n{water_bar} {water_pct}%\n"
    response += f"Выпито: {u['logged_water']:.0f} мл из {u['water_goal']} мл\n"
    
    if u['logged_water'] >= u['water_goal']:
        response += "✅ Норма воды выполнена!\n"
    else:
        response += f"Осталось: {u['water_goal'] - u['logged_water']:.0f} мл\n"
    
    response += "\n🔥 Калории:\n"
    response += f"{calorie_bar} {calorie_pct}%\n"
    response += f"Потреблено: {u['logged_calories']:.0f} ккал\n"
    response += f"Сожжено: {u['burned_calories']:.0f} ккал\n"
    response += f"Баланс: {net_calories:.0f} ккал из {u['calorie_goal']} ккал\n"
    
    if net_calories > u['calorie_goal']:
        response += "⚠️ Превышение нормы калорий!"
    elif net_calories >= u['calorie_goal'] * 0.9:
        response += "✅ Норма почти выполнена!"
    
    # Добавляем рекомендации
    rec_text = format_recommendations(message.from_user.id)
    if rec_text:
        response += f"\n\n💡 Рекомендации:{rec_text}"
        await message.answer(response, parse_mode="HTML", reply_markup=get_recommendation_buttons(message.from_user.id))
    else:
        await message.answer(response)


@router.message(Command("show_stats"))
async def show_stats(message: Message):
    ensure_user_exists(message.from_user.id)
    reset_daily_data(message.from_user.id)
    
    if not is_profile_complete(message.from_user.id):
        await message.answer(
            "⚠️ Сначала настройте профиль командой /set_profile",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настроить профиль", callback_data="set_profile")]
            ])
        )
        return
    
    save_daily_stats(message.from_user.id)
    chart_buffer = create_progress_charts(message.from_user.id)
    
    if not chart_buffer:
        await message.answer(
            "📉 Недостаточно данных для построения графика.\n"
            "Запишите хотя бы один день воды или калорий!"
        )
        return
    
    photo = BufferedInputFile(chart_buffer.read(), filename="progress.png")
    caption = "📈 Ваш недельный прогресс по воде и калориям"
    
    # Добавляем рекомендации к графику
    rec_text = format_recommendations(message.from_user.id)
    if rec_text:
        caption += f"\n\n💡 Советы:{rec_text}"
        await message.answer_photo(
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=get_recommendation_buttons(message.from_user.id)
        )
    else:
        await message.answer_photo(photo=photo, caption=caption)


@router.message(Command("recommend"))
async def recommend(message: Message):
    ensure_user_exists(message.from_user.id)
    reset_daily_data(message.from_user.id)
    
    if not is_profile_complete(message.from_user.id):
        await message.answer(
            "⚠️ Сначала настройте профиль командой /set_profile",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔧 Настроить профиль", callback_data="set_profile")]
            ])
        )
        return
    
    rec_text = format_recommendations(message.from_user.id)
    
    if not rec_text:
        # Если нет рекомендаций — показываем позитивный фидбек
        u = users[message.from_user.id]
        net = u['logged_calories'] - u['burned_calories']
        if abs(net - u['calorie_goal']) / u['calorie_goal'] < 0.1:
            await message.answer(
                "🌟 Отлично! Вы в идеальном балансе:\n"
                "• Вода и калории в норме\n"
                "• Продолжайте в том же духе!"
            )
        else:
            await message.answer(
                "💡 Сейчас у вас хороший баланс.\n"
                "Рекомендации появятся, когда:\n"
                "• Недобор калорий > 15% от нормы, или\n"
                "• Превышение калорий > 20% от нормы"
            )
        return
    
    await message.answer(
        f"💡 Персональные рекомендации:\n{rec_text}",
        parse_mode="HTML",
        reply_markup=get_recommendation_buttons(message.from_user.id)
    )


@router.message(Command("help"))
async def help_cmd(message: Message):
    help_text = (
        "📖 Справка по командам:\n\n"
        "• /set_profile — настроить профиль (вес, рост, возраст, пол, активность, город)\n"
        "• /view_profile — посмотреть текущие настройки профиля\n"
        "• /log_water — записать выпитую воду\n"
        "• /log_food — записать съеденный продукт\n"
        "• /log_workout — записать тренировку\n"
        "• /check_progress — показать прогресс за день\n"
        "• /show_stats — 📈 графики прогресса за неделю\n"
        "• /recommend — 💡 получить персональные рекомендации еды или тренировок\n"
        "• /cancel — отменить текущую операцию ввода"
    )
    await message.answer(help_text, reply_markup=get_cancel_help_buttons())


@router.message()
async def unknown(message: Message):
    await message.answer(
        "❓ Неизвестная команда.\nИспользуйте /help для просмотра доступных команд.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="show_help"),
                InlineKeyboardButton(text="💡 Рекомендации", callback_data="recommend_now")
            ]
        ])
    )


@router.callback_query(lambda c: c.data == "recommend_now")
async def recommend_now(callback: CallbackQuery):
    await callback.answer()
    await recommend(callback.message)


def setup_handlers(dp):
    dp.include_router(router)