import os
from pathlib import Path

# Путь к папке с картинками
IMAGES_DIR = Path(__file__).parent / "images"

# Словарь картинок для разделов
MENU_IMAGES = {
    "main_menu": IMAGES_DIR / "main_menu.png",
    "add_deal": IMAGES_DIR / "add_deal.png",
    "stats": IMAGES_DIR / "stats.png",
    "analytics": IMAGES_DIR / "analytics.png",
    "charts": IMAGES_DIR / "charts.png",
    "export": IMAGES_DIR / "export.png",
    "converter": IMAGES_DIR / "converter.png",
    "settings": IMAGES_DIR / "settings.png",
}


def get_image_path(section: str) -> str:
    """Получить путь к картинке раздела"""
    path = MENU_IMAGES.get(section)
    if path and path.exists():
        return str(path)
    return None


def image_exists(section: str) -> bool:
    """Проверить существует ли картинка"""
    path = MENU_IMAGES.get(section)
    return path is not None and path.exists()
