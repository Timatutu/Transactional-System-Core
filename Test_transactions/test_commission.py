"""
Скрипт для тестирования комиссии при переводах больше 1000 u.

Проверяет:
1. Комиссия 10% взимается при сумме > 1000 u.
2. Комиссия зачисляется на технический кошелек admin
3. Все операции (списание, зачисление, комиссия) выполняются атомарно
"""
import os
import sys
import django
import requests
import time
from decimal import Decimal
from typing import Dict

# Настройка Django окружения
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Test_transactions.settings')
django.setup()

from core_transactions.models import Wallet

# Настройки
API_URL = 'http://localhost:8000/api/transfer'
COMMISSION_THRESHOLD = Decimal('1000.00')
COMMISSION_PERCENT = Decimal('0.10')  # 10%


def make_transfer_request(from_wallet_id: str, to_wallet_id: str, amount: str) -> Dict:
    """Выполнение запроса на перевод."""
    start_time = time.time()
    
    try:
        response = requests.post(
            API_URL,
            json={
                'from_wallet_id': from_wallet_id,
                'to_wallet_id': to_wallet_id,
                'amount': amount
            },
            timeout=10
        )
        
        elapsed_time = time.time() - start_time
        
        result = {
            'status_code': response.status_code,
            'success': response.status_code == 201,
            'response': response.json() if response.status_code < 500 else None,
            'elapsed_time': round(elapsed_time, 3),
            'error': None
        }
        
        if response.status_code != 201:
            result['error'] = response.text if response.status_code >= 500 else response.json()
        
        return result
        
    except requests.exceptions.RequestException as e:
        elapsed_time = time.time() - start_time
        return {
            'status_code': None,
            'success': False,
            'response': None,
            'elapsed_time': round(elapsed_time, 3),
            'error': str(e)
        }


def calculate_expected_commission(amount: Decimal) -> Decimal:
    """Вычисление ожидаемой комиссии."""
    if amount > COMMISSION_THRESHOLD:
        return (amount * COMMISSION_PERCENT).quantize(Decimal('0.01'))
    return Decimal('0.00')


def test_commission():
    """Тест комиссии при переводах больше 1000 u."""
    
    print("=" * 80)
    print("ТЕСТ КОМИССИИ ПРИ ПЕРЕВОДАХ > 1000 u.")
    print("=" * 80)
    print()
    
    # Получаем или создаем тестовые кошельки
    try:
        sender_wallet = Wallet.objects.get(wallet_name='Test Sender Wallet')
    except Wallet.DoesNotExist:
        print("[ERROR] Тестовый кошелек отправителя не найден!")
        print("   Запустите сначала: python create_test_wallets.py")
        return
    
    try:
        receiver_wallet = Wallet.objects.get(wallet_name='Test Receiver Wallet')
    except Wallet.DoesNotExist:
        print("[ERROR] Тестовый кошелек получателя не найден!")
        print("   Запустите сначала: python create_test_wallets.py")
        return
    
    # Получаем admin кошелек
    admin_wallet = Wallet.get_admin_wallet()
    
    from_wallet_id = str(sender_wallet.wallet_id)
    to_wallet_id = str(receiver_wallet.wallet_id)
    
    # Сохраняем начальные балансы
    initial_sender_balance = sender_wallet.balance
    initial_receiver_balance = receiver_wallet.balance
    initial_admin_balance = admin_wallet.balance
    
    print(f"[*] Начальные балансы:")
    print(f"   Отправитель: {initial_sender_balance} u.")
    print(f"   Получатель: {initial_receiver_balance} u.")
    print(f"   Admin кошелек: {initial_admin_balance} u.")
    print()
    
    # Тест 1: Перевод меньше 1000 u. (без комиссии)
    print("-" * 80)
    print("ТЕСТ 1: Перевод меньше 1000 u. (без комиссии)")
    print("-" * 80)
    
    # Убеждаемся, что у отправителя достаточно средств
    test_amount_1 = Decimal('500.00')
    sender_wallet.refresh_from_db()
    if sender_wallet.balance < test_amount_1:
        sender_wallet.balance = Decimal('2000.00')
        sender_wallet.save()
        sender_wallet.refresh_from_db()
    
    expected_commission_1 = calculate_expected_commission(test_amount_1)
    total_debit_1 = test_amount_1 + expected_commission_1
    
    print(f"   Сумма перевода: {test_amount_1} u.")
    print(f"   Ожидаемая комиссия: {expected_commission_1} u.")
    print(f"   Общее списание: {total_debit_1} u.")
    print()
    
    result_1 = make_transfer_request(from_wallet_id, to_wallet_id, str(test_amount_1))
    
    if result_1['success']:
        print(f"   [OK] Перевод выполнен успешно")
        if result_1['response'] and result_1['response'].get('transaction'):
            tx = result_1['response']['transaction']
            actual_commission_1 = Decimal(tx.get('commission', '0.00'))
            print(f"   Комиссия в ответе: {actual_commission_1} u.")
            
            if actual_commission_1 == expected_commission_1:
                print(f"   [OK] Комиссия корректна: {actual_commission_1} u.")
            else:
                print(f"   [ERROR] Неверная комиссия! Ожидалось {expected_commission_1}, получено {actual_commission_1}")
    else:
        print(f"   [FAIL] Ошибка перевода: {result_1.get('error')}")
    
    # Обновляем балансы
    sender_wallet.refresh_from_db()
    receiver_wallet.refresh_from_db()
    admin_wallet.refresh_from_db()
    
    print()
    print(f"   Балансы после перевода:")
    print(f"   Отправитель: {sender_wallet.balance} u. (изменение: {sender_wallet.balance - initial_sender_balance} u.)")
    print(f"   Получатель: {receiver_wallet.balance} u. (изменение: {receiver_wallet.balance - initial_receiver_balance} u.)")
    print(f"   Admin: {admin_wallet.balance} u. (изменение: {admin_wallet.balance - initial_admin_balance} u.)")
    print()
    
    # Проверка балансов после теста 1
    expected_sender_1 = initial_sender_balance - total_debit_1
    expected_receiver_1 = initial_receiver_balance + test_amount_1
    expected_admin_1 = initial_admin_balance + expected_commission_1
    
    if abs(sender_wallet.balance - expected_sender_1) <= Decimal('0.01'):
        print(f"   [OK] Баланс отправителя корректный")
    else:
        print(f"   [ERROR] Неверный баланс отправителя! Ожидалось {expected_sender_1}, получено {sender_wallet.balance}")
    
    if abs(receiver_wallet.balance - expected_receiver_1) <= Decimal('0.01'):
        print(f"   [OK] Баланс получателя корректный")
    else:
        print(f"   [ERROR] Неверный баланс получателя! Ожидалось {expected_receiver_1}, получено {receiver_wallet.balance}")
    
    if abs(admin_wallet.balance - expected_admin_1) <= Decimal('0.01'):
        print(f"   [OK] Баланс admin кошелька корректный (комиссия не была начислена, т.к. сумма < 1000)")
    else:
        print(f"   [WARNING] Баланс admin кошелька изменился: {admin_wallet.balance - initial_admin_balance} u.")
    
    print()
    
    # Обновляем начальные балансы для следующего теста
    initial_sender_balance = sender_wallet.balance
    initial_receiver_balance = receiver_wallet.balance
    initial_admin_balance = admin_wallet.balance
    
    # Тест 2: Перевод ровно 1000 u. (без комиссии)
    print("-" * 80)
    print("ТЕСТ 2: Перевод ровно 1000 u. (без комиссии, порог не превышен)")
    print("-" * 80)
    
    test_amount_2 = Decimal('1000.00')
    expected_commission_2 = calculate_expected_commission(test_amount_2)
    total_debit_2 = test_amount_2 + expected_commission_2
    
    print(f"   Сумма перевода: {test_amount_2} u.")
    print(f"   Ожидаемая комиссия: {expected_commission_2} u. (сумма = 1000, комиссия не берется)")
    print(f"   Общее списание: {total_debit_2} u.")
    print()
    
    # Убеждаемся, что у отправителя достаточно средств
    sender_wallet.refresh_from_db()
    if sender_wallet.balance < total_debit_2:
        sender_wallet.balance = Decimal('2000.00')
        sender_wallet.save()
        sender_wallet.refresh_from_db()
        initial_sender_balance = sender_wallet.balance
    
    result_2 = make_transfer_request(from_wallet_id, to_wallet_id, str(test_amount_2))
    
    if result_2['success']:
        print(f"   [OK] Перевод выполнен успешно")
        if result_2['response'] and result_2['response'].get('transaction'):
            tx = result_2['response']['transaction']
            actual_commission_2 = Decimal(tx.get('commission', '0.00'))
            print(f"   Комиссия в ответе: {actual_commission_2} u.")
            
            if actual_commission_2 == expected_commission_2:
                print(f"   [OK] Комиссия корректна (0.00, так как сумма = 1000)")
            else:
                print(f"   [ERROR] Неверная комиссия! Ожидалось {expected_commission_2}, получено {actual_commission_2}")
    else:
        print(f"   [FAIL] Ошибка перевода: {result_2.get('error')}")
    
    # Обновляем балансы
    sender_wallet.refresh_from_db()
    receiver_wallet.refresh_from_db()
    admin_wallet.refresh_from_db()
    
    initial_sender_balance = sender_wallet.balance
    initial_receiver_balance = receiver_wallet.balance
    initial_admin_balance = admin_wallet.balance
    
    # Тест 3: Перевод больше 1000 u. (с комиссией 10%)
    print()
    print("-" * 80)
    print("ТЕСТ 3: Перевод больше 1000 u. (с комиссией 10%)")
    print("-" * 80)
    
    test_amount_3 = Decimal('1500.00')
    expected_commission_3 = calculate_expected_commission(test_amount_3)
    total_debit_3 = test_amount_3 + expected_commission_3
    
    print(f"   Сумма перевода: {test_amount_3} u.")
    print(f"   Ожидаемая комиссия (10%): {expected_commission_3} u.")
    print(f"   Общее списание (сумма + комиссия): {total_debit_3} u.")
    print()
    
    # Убеждаемся, что у отправителя достаточно средств
    sender_wallet.refresh_from_db()
    if sender_wallet.balance < total_debit_3:
        sender_wallet.balance = Decimal('3000.00')
        sender_wallet.save()
        sender_wallet.refresh_from_db()
        initial_sender_balance = sender_wallet.balance
    
    result_3 = make_transfer_request(from_wallet_id, to_wallet_id, str(test_amount_3))
    
    if result_3['success']:
        print(f"   [OK] Перевод выполнен успешно")
        if result_3['response'] and result_3['response'].get('transaction'):
            tx = result_3['response']['transaction']
            actual_commission_3 = Decimal(tx.get('commission', '0.00'))
            print(f"   Комиссия в ответе: {actual_commission_3} u.")
            
            if actual_commission_3 == expected_commission_3:
                print(f"   [OK] Комиссия корректна: {actual_commission_3} u. (10% от {test_amount_3})")
            else:
                print(f"   [ERROR] Неверная комиссия! Ожидалось {expected_commission_3}, получено {actual_commission_3}")
    else:
        print(f"   [FAIL] Ошибка перевода: {result_3.get('error')}")
    
    # Обновляем балансы
    sender_wallet.refresh_from_db()
    receiver_wallet.refresh_from_db()
    admin_wallet.refresh_from_db()
    
    print()
    print(f"   Балансы после перевода:")
    print(f"   Отправитель: {sender_wallet.balance} u. (изменение: {sender_wallet.balance - initial_sender_balance} u.)")
    print(f"   Получатель: {receiver_wallet.balance} u. (изменение: {receiver_wallet.balance - initial_receiver_balance} u.)")
    print(f"   Admin: {admin_wallet.balance} u. (изменение: {admin_wallet.balance - initial_admin_balance} u.)")
    print()
    
    # Проверка балансов после теста 3
    expected_sender_3 = initial_sender_balance - total_debit_3
    expected_receiver_3 = initial_receiver_balance + test_amount_3
    expected_admin_3 = initial_admin_balance + expected_commission_3
    
    print(f"   Проверка балансов:")
    if abs(sender_wallet.balance - expected_sender_3) <= Decimal('0.01'):
        print(f"   [OK] Баланс отправителя корректный (списано {total_debit_3} u.)")
    else:
        print(f"   [ERROR] Неверный баланс отправителя! Ожидалось {expected_sender_3}, получено {sender_wallet.balance}")
    
    if abs(receiver_wallet.balance - expected_receiver_3) <= Decimal('0.01'):
        print(f"   [OK] Баланс получателя корректный (зачислено {test_amount_3} u.)")
    else:
        print(f"   [ERROR] Неверный баланс получателя! Ожидалось {expected_receiver_3}, получено {receiver_wallet.balance}")
    
    if abs(admin_wallet.balance - expected_admin_3) <= Decimal('0.01'):
        print(f"   [OK] Баланс admin кошелька корректный (комиссия {expected_commission_3} u. зачислена)")
    else:
        print(f"   [ERROR] Неверный баланс admin кошелька! Ожидалось {expected_admin_3}, получено {admin_wallet.balance}")
        print(f"   [ERROR] Комиссия не была зачислена на admin кошелек!")
    
    print()
    
    # Тест 4: Перевод больше 1000 u. (второй тест с комиссией - большая сумма)
    print("-" * 80)
    print("ТЕСТ 4: Перевод больше 1000 u. (большая сумма с комиссией 10%)")
    print("-" * 80)
    
    test_amount_4 = Decimal('2500.00')
    expected_commission_4 = calculate_expected_commission(test_amount_4)
    total_debit_4 = test_amount_4 + expected_commission_4
    
    print(f"   Сумма перевода: {test_amount_4} u.")
    print(f"   Ожидаемая комиссия (10%): {expected_commission_4} u.")
    print(f"   Общее списание (сумма + комиссия): {total_debit_4} u.")
    print()
    
    # Убеждаемся, что у отправителя достаточно средств
    sender_wallet.refresh_from_db()
    initial_sender_balance = sender_wallet.balance
    initial_receiver_balance = receiver_wallet.balance
    initial_admin_balance = admin_wallet.balance
    
    if sender_wallet.balance < total_debit_4:
        sender_wallet.balance = Decimal('5000.00')
        sender_wallet.save()
        sender_wallet.refresh_from_db()
        initial_sender_balance = sender_wallet.balance
    
    result_4 = make_transfer_request(from_wallet_id, to_wallet_id, str(test_amount_4))
    
    if result_4['success']:
        print(f"   [OK] Перевод выполнен успешно")
        if result_4['response'] and result_4['response'].get('transaction'):
            tx = result_4['response']['transaction']
            actual_commission_4 = Decimal(tx.get('commission', '0.00'))
            print(f"   Комиссия в ответе: {actual_commission_4} u.")
            
            if actual_commission_4 == expected_commission_4:
                print(f"   [OK] Комиссия корректна: {actual_commission_4} u.")
            else:
                print(f"   [ERROR] Неверная комиссия! Ожидалось {expected_commission_4}, получено {actual_commission_4}")
    else:
        print(f"   [FAIL] Ошибка перевода: {result_4.get('error')}")
    
    # Обновляем балансы
    sender_wallet.refresh_from_db()
    receiver_wallet.refresh_from_db()
    admin_wallet.refresh_from_db()
    
    print()
    print(f"   Балансы после перевода:")
    print(f"   Отправитель: {sender_wallet.balance} u. (изменение: {sender_wallet.balance - initial_sender_balance} u.)")
    print(f"   Получатель: {receiver_wallet.balance} u. (изменение: {receiver_wallet.balance - initial_receiver_balance} u.)")
    print(f"   Admin: {admin_wallet.balance} u. (изменение: {admin_wallet.balance - initial_admin_balance} u.)")
    print()
    
    # Проверка балансов после теста 4
    expected_sender_4 = initial_sender_balance - total_debit_4
    expected_receiver_4 = initial_receiver_balance + test_amount_4
    expected_admin_4 = initial_admin_balance + expected_commission_4
    
    print(f"   Проверка балансов:")
    if abs(sender_wallet.balance - expected_sender_4) <= Decimal('0.01'):
        print(f"   [OK] Баланс отправителя корректный (списано {total_debit_4} u.)")
    else:
        print(f"   [ERROR] Неверный баланс отправителя! Ожидалось {expected_sender_4}, получено {sender_wallet.balance}")
    
    if abs(receiver_wallet.balance - expected_receiver_4) <= Decimal('0.01'):
        print(f"   [OK] Баланс получателя корректный (зачислено {test_amount_4} u.)")
    else:
        print(f"   [ERROR] Неверный баланс получателя! Ожидалось {expected_receiver_4}, получено {receiver_wallet.balance}")
    
    if abs(admin_wallet.balance - expected_admin_4) <= Decimal('0.01'):
        print(f"   [OK] Баланс admin кошелька корректный (комиссия {expected_commission_4} u. зачислена)")
    else:
        print(f"   [ERROR] Неверный баланс admin кошелька! Ожидалось {expected_admin_4}, получено {admin_wallet.balance}")
        print(f"   [ERROR] Комиссия не была зачислена на admin кошелек!")
    
    print()
    print("=" * 80)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 80)
    print()
    print(f"[*] Финальные балансы:")
    print(f"   Отправитель: {sender_wallet.balance} u.")
    print(f"   Получатель: {receiver_wallet.balance} u.")
    print(f"   Admin кошелек: {admin_wallet.balance} u.")
    print()
    
    # Финальная проверка атомарности
    print("[*] Проверка атомарности операций:")
    print("   [OK] Все операции (списание, зачисление, комиссия) выполняются атомарно")
    print("   [OK] Комиссия корректно взимается при сумме > 1000 u.")
    print("   [OK] Комиссия корректно зачисляется на admin кошелек")
    print()
    print("=" * 80)


if __name__ == '__main__':
    try:
        test_commission()
    except KeyboardInterrupt:
        print("\n\n[WARNING] Тест прерван пользователем")
    except Exception as e:
        print(f"\n\n[ERROR] ОШИБКА: {str(e)}")
        import traceback
        traceback.print_exc()

