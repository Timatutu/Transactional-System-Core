"""
Скрипт для тестирования защиты от race condition (Double Spending).

Делает 10 одновременных запросов на списание средств с одного кошелька,
чтобы проверить, что баланс не уйдет в минус.

Использование:
    python test_race_condition.py
"""
import os
import sys
import django
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from typing import Dict

# Настройка Django окружения
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Test_transactions.settings')
django.setup()

from core_transactions.models import Wallet

# Настройки
API_URL = 'http://localhost:8000/api/transfer'
NUM_REQUESTS = 10  # Количество одновременных запросов
AMOUNT_PER_REQUEST = Decimal('10.00')  # Сумма каждого перевода


def make_transfer_request(from_wallet_id: str, to_wallet_id: str, amount: str, request_num: int) -> Dict:
    """Выполнение одного запроса на перевод."""
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
            'request_num': request_num,
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
            'request_num': request_num,
            'status_code': None,
            'success': False,
            'response': None,
            'elapsed_time': round(elapsed_time, 3),
            'error': str(e)
        }


def test_race_condition():
    """Основная функция тестирования race condition"""
    
    print("=" * 80)
    print("ТЕСТ ЗАЩИТЫ ОТ RACE CONDITION (DOUBLE SPENDING)")
    print("=" * 80)
    print()
    
    # Получаем тестовые кошельки
    try:
        sender_wallet = Wallet.objects.get(wallet_name='Test Sender Wallet')
        receiver_wallet = Wallet.objects.get(wallet_name='Test Receiver Wallet')
    except Wallet.DoesNotExist:
        print("[ERROR] Тестовые кошельки не найдены!")
        print("   Запустите сначала: python create_test_wallets.py")
        return
    
    from_wallet_id = str(sender_wallet.wallet_id)
    to_wallet_id = str(receiver_wallet.wallet_id)
    
    # Показываем начальное состояние
    initial_sender_balance = sender_wallet.balance
    initial_receiver_balance = receiver_wallet.balance
    total_amount = NUM_REQUESTS * AMOUNT_PER_REQUEST
    
    print(f"[*] Начальное состояние:")
    print(f"   Кошелек отправителя: {sender_wallet.wallet_name}")
    print(f"   ID: {from_wallet_id}")
    print(f"   Баланс: {initial_sender_balance} u.")
    print()
    print(f"   Кошелек получателя: {receiver_wallet.wallet_name}")
    print(f"   ID: {to_wallet_id}")
    print(f"   Баланс: {initial_receiver_balance} u.")
    print()
    print(f"[*] Параметры теста:")
    print(f"   Количество запросов: {NUM_REQUESTS}")
    print(f"   Сумма каждого перевода: {AMOUNT_PER_REQUEST} u.")
    print(f"   Общая сумма всех переводов: {total_amount} u.")
    print(f"   Доступный баланс: {initial_sender_balance} u.")
    print()
    
    if initial_sender_balance < total_amount:
        print(f"[WARNING] Общая сумма ({total_amount} u.) больше баланса ({initial_sender_balance} u.)")
        print(f"   Это нормально - мы проверяем защиту от overspending!")
        print()
    
    print("[*] Запуск одновременных запросов...")
    print()
    
    # Выполняем запросы параллельно
    start_time = time.time()
    results = []
    
    with ThreadPoolExecutor(max_workers=NUM_REQUESTS) as executor:
        # Создаем все задачи
        futures = [
            executor.submit(
                make_transfer_request,
                from_wallet_id,
                to_wallet_id,
                str(AMOUNT_PER_REQUEST),
                i + 1
            )
            for i in range(NUM_REQUESTS)
        ]
        
        # Собираем результаты по мере выполнения
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            
            status_icon = "[OK]" if result['success'] else "[FAIL]"
            print(f"{status_icon} Запрос #{result['request_num']:2d}: "
                  f"Статус {result['status_code']}, "
                  f"Время {result['elapsed_time']:.3f}с")
            
            if not result['success'] and result.get('error'):
                if isinstance(result['error'], dict) and 'message' in result['error']:
                    print(f"   [WARNING] {result['error']['message']}")
                else:
                    print(f"   [WARNING] {result['error']}")
    
    total_time = time.time() - start_time
    
    print()
    print("=" * 80)
    print("РЕЗУЛЬТАТЫ ТЕСТА")
    print("=" * 80)
    print()
    
    # Подсчитываем статистику
    successful = sum(1 for r in results if r['success'])
    failed = NUM_REQUESTS - successful
    
    print(f"[*] Статистика запросов:")
    print(f"   Успешных: {successful}/{NUM_REQUESTS}")
    print(f"   Отклоненных: {failed}/{NUM_REQUESTS}")
    print(f"   Общее время: {total_time:.3f} секунд")
    print(f"   Среднее время на запрос: {total_time/NUM_REQUESTS:.3f} секунд")
    print()
    
    # Проверяем финальное состояние кошельков
    sender_wallet.refresh_from_db()
    receiver_wallet.refresh_from_db()
    
    final_sender_balance = sender_wallet.balance
    final_receiver_balance = receiver_wallet.balance
    
    print(f"[*] Финальное состояние кошельков:")
    print(f"   Отправитель:")
    print(f"      Начальный баланс: {initial_sender_balance} u.")
    print(f"      Финальный баланс: {final_sender_balance} u.")
    print(f"      Изменение: {final_sender_balance - initial_sender_balance} u.")
    print()
    print(f"   Получатель:")
    print(f"      Начальный баланс: {initial_receiver_balance} u.")
    print(f"      Финальный баланс: {final_receiver_balance} u.")
    print(f"      Изменение: {final_receiver_balance - initial_receiver_balance} u.")
    print()
    
    # Проверяем, что баланс не ушел в минус
    is_negative = final_sender_balance < Decimal('0.00')
    
    # Подсчитываем сумму успешных транзакций
    expected_debit = successful * AMOUNT_PER_REQUEST
    actual_debit = initial_sender_balance - final_sender_balance
    
    print(f"[*] Проверка защиты от race condition:")
    print(f"   Успешных переводов: {successful}")
    print(f"   Ожидаемое списание: {expected_debit} u.")
    print(f"   Фактическое списание: {actual_debit} u.")
    print()
    
    if is_negative:
        print("[ERROR] КРИТИЧЕСКАЯ ОШИБКА: Баланс ушел в минус!")
        print(f"   Баланс: {final_sender_balance} u.")
        print("   Защита от race condition НЕ РАБОТАЕТ!")
    else:
        print("[OK] УСПЕХ: Баланс не ушел в минус!")
        print(f"   Баланс: {final_sender_balance} u. (>= 0)")
    
    if successful < NUM_REQUESTS:
        print()
        print(f"[OK] УСПЕХ: Система правильно отклонила {failed} запросов из-за недостатка средств")
        print(f"   Это подтверждает работу защиты от overspending!")
    
    if abs(actual_debit - expected_debit) <= Decimal('0.01'):
        print()
        print("[OK] УСПЕХ: Сумма списаний соответствует количеству успешных транзакций")
    else:
        print()
        print(f"[WARNING] Разница между ожидаемым и фактическим списанием: "
              f"{abs(actual_debit - expected_debit)} u.")
    
    print()
    print("=" * 80)
    
    # Показываем детали каждой транзакции
    print("\n[*] Детали транзакций:")
    print("-" * 80)
    for result in sorted(results, key=lambda x: x['request_num']):
        status = "[OK] УСПЕХ" if result['success'] else "[FAIL] ОТКЛОНЕНО"
        print(f"Запрос #{result['request_num']:2d}: {status} "
              f"(Статус: {result['status_code']}, Время: {result['elapsed_time']:.3f}с)")
        if result.get('response') and result['response'].get('transaction'):
            tx = result['response']['transaction']
            print(f"   ID транзакции: {tx.get('transaction_id')}")
            print(f"   Сумма: {tx.get('amount')} u., Комиссия: {tx.get('commission')} u.")
    
    print()
    print("=" * 80)


if __name__ == '__main__':
    try:
        test_race_condition()
    except KeyboardInterrupt:
        print("\n\n[WARNING] Тест прерван пользователем")
    except Exception as e:
        print(f"\n\n[ERROR] ОШИБКА: {str(e)}")
        import traceback
        traceback.print_exc()
