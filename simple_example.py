"""
Простой пример работы с функциями и списками
Демонстрирует базовые операции с данными
"""


def calculate_average(numbers):
    """Вычисляет среднее значение списка чисел"""
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)


def filter_even_numbers(numbers):
    """Фильтрует четные числа из списка"""
    return [num for num in numbers if num % 2 == 0]


def find_max_min(numbers):
    """Находит максимальное и минимальное значение"""
    if not numbers:
        return None, None
    return max(numbers), min(numbers)


def count_words(text):
    """Подсчитывает количество слов в тексте"""
    words = text.split()
    return len(words)


def greet_user(name, age=None):
    """Приветствует пользователя"""
    if age:
        return f"Привет, {name}! Тебе {age} лет."
    return f"Привет, {name}!"


def main():
    """Основная функция для демонстрации"""
    
    # Работа с числами
    numbers = [15, 23, 8, 42, 7, 31, 19, 56, 3, 28]
    print("Исходный список чисел:", numbers)
    print()
    
    # Среднее значение
    average = calculate_average(numbers)
    print(f"Среднее значение: {average:.2f}")
    
    # Четные числа
    even_numbers = filter_even_numbers(numbers)
    print(f"Четные числа: {even_numbers}")
    
    # Максимум и минимум
    maximum, minimum = find_max_min(numbers)
    print(f"Максимум: {maximum}, Минимум: {minimum}")
    print()
    
    # Работа с текстом
    text = "Python это отличный язык программирования"
    word_count = count_words(text)
    print(f"Текст: '{text}'")
    print(f"Количество слов: {word_count}")
    print()
    
    # Приветствия
    print(greet_user("Анна"))
    print(greet_user("Иван", 25))
    print()
    
    # Дополнительные операции
    squared = [x ** 2 for x in numbers[:5]]
    print(f"Первые 5 чисел в квадрате: {squared}")


if __name__ == "__main__":
    main()
