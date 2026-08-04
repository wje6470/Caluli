"""所有 model 於此匯入，供 Alembic autogenerate 掃描。"""

from app.db.base import Base
from app.db.models.food_reference import FoodNutritionReference, normalize_food_name
from app.db.models.health_profile import ACTIVITY_LEVELS, GENDERS, HealthProfile
from app.db.models.meal_item import MealItem
from app.db.models.meal_record import MEAL_TYPES, MealRecord
from app.db.models.menu_item import MenuItem
from app.db.models.recognition_job import (
    ERROR_BAD_RESPONSE,
    ERROR_TIMEOUT,
    ERROR_UNAVAILABLE,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    RecognitionJob,
)
from app.db.models.store import Store
from app.db.models.user import ROLE_ADMIN, ROLE_USER, User

__all__ = [
    "ACTIVITY_LEVELS",
    "ERROR_BAD_RESPONSE",
    "ERROR_TIMEOUT",
    "ERROR_UNAVAILABLE",
    "GENDERS",
    "MEAL_TYPES",
    "ROLE_ADMIN",
    "ROLE_USER",
    "STATUS_COMPLETED",
    "STATUS_FAILED",
    "STATUS_PROCESSING",
    "Base",
    "FoodNutritionReference",
    "HealthProfile",
    "MealItem",
    "MealRecord",
    "MenuItem",
    "RecognitionJob",
    "Store",
    "User",
    "normalize_food_name",
]
