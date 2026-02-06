from aiogram.fsm.state import State, StatesGroup

class ProfileForm(StatesGroup):
    weight = State()
    height = State()
    age = State()
    gender = State()
    activity = State()
    city = State()

class FoodForm(StatesGroup):
    grams = State()

class WaterForm(StatesGroup):
    amount = State()  # Ожидание количества воды в мл

class FoodForm(StatesGroup):
    product = State()  # Ожидание названия продукта
    grams = State()    # Ожидание граммовки

class WorkoutForm(StatesGroup):
    type = State()     # Ожидание типа тренировки
    duration = State() # Ожидание длительности в минутах
