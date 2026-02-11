"""
Простой пример работы с классами и декораторами
Демонстрирует обработку данных о продуктах с валидацией
"""

from typing import List, Dict
from functools import wraps
from datetime import datetime


def validate_price(func):
    """Декоратор для валидации цены продукта"""
    @wraps(func)
    def wrapper(self, price):
        if price < 0:
            raise ValueError("Цена не может быть отрицательной")
        if price > 1000000:
            raise ValueError("Цена слишком высокая")
        return func(self, price)
    return wrapper


class Product:
    """Класс для представления продукта"""
    
    def __init__(self, name: str, price: float, category: str = "Общее"):
        self.name = name
        self._price = price
        self.category = category
        self.created_at = datetime.now()
    
    @property
    def price(self):
        return self._price
    
    @price.setter
    @validate_price
    def price(self, value: float):
        self._price = value
    
    def apply_discount(self, percent: float) -> float:
        """Применяет скидку к цене"""
        if not 0 <= percent <= 100:
            raise ValueError("Скидка должна быть от 0 до 100%")
        discount_amount = self._price * (percent / 100)
        self._price = round(self._price - discount_amount, 2)
        return self._price
    
    def __str__(self):
        return f"{self.name} ({self.category}): {self._price}₽"
    
    def __repr__(self):
        return f"Product('{self.name}', {self._price}, '{self.category}')"


class Store:
    """Класс для управления магазином продуктов"""
    
    def __init__(self, name: str):
        self.name = name
        self.products: List[Product] = []
    
    def add_product(self, product: Product):
        """Добавляет продукт в магазин"""
        self.products.append(product)
        print(f"✓ Добавлен: {product}")
    
    def get_total_value(self) -> float:
        """Возвращает общую стоимость всех продуктов"""
        return sum(product.price for product in self.products)
    
    def get_products_by_category(self, category: str) -> List[Product]:
        """Возвращает продукты по категории"""
        return [p for p in self.products if p.category == category]
    
    def apply_category_discount(self, category: str, percent: float):
        """Применяет скидку ко всем продуктам категории"""
        products = self.get_products_by_category(category)
        for product in products:
            product.apply_discount(percent)
        print(f"Скидка {percent}% применена к категории '{category}'")
    
    def print_inventory(self):
        """Выводит инвентарь магазина"""
        print(f"\n{'='*50}")
        print(f"Магазин: {self.name}")
        print(f"{'='*50}")
        for product in self.products:
            print(f"  {product}")
        print(f"{'='*50}")
        print(f"Общая стоимость: {self.get_total_value():.2f}₽")
        print()


def main():
    """Основная функция для демонстрации"""
    # Создаем магазин
    store = Store("ТехноМарт")
    
    # Создаем продукты
    products_data = [
        ("Ноутбук", 75000, "Электроника"),
        ("Мышь", 1500, "Электроника"),
        ("Стол", 12000, "Мебель"),
        ("Стул", 5000, "Мебель"),
        ("Книга", 800, "Книги"),
    ]
    
    # Добавляем продукты в магазин
    for name, price, category in products_data:
        product = Product(name, price, category)
        store.add_product(product)
    
    # Выводим инвентарь
    store.print_inventory()
    
    # Применяем скидку на электронику
    store.apply_category_discount("Электроника", 15)
    
    # Выводим обновленный инвентарь
    store.print_inventory()
    
    # Демонстрация работы с отдельным продуктом
    laptop = store.products[0]
    print(f"Исходная цена ноутбука: {laptop.price}₽")
    laptop.apply_discount(10)
    print(f"Цена после скидки 10%: {laptop.price}₽")
    
    # Попытка установить невалидную цену (будет ошибка)
    try:
        laptop.price = -100
    except ValueError as e:
        print(f"Ошибка валидации: {e}")


if __name__ == "__main__":
    main()
