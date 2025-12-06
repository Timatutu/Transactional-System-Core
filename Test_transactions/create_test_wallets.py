"""
Скрипт для создания тестовых кошельков для проверки race condition.

Использование:
    python create_test_wallets.py
"""
import os
import sys
import django
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Test_transactions.settings')
django.setup()

from core_transactions.models import Wallet


def create_test_wallets():
    """Создание тестовых кошельков для проверки race condition"""
    
    # Кошелек отправителя с балансом 100 u.
    # Будем пытаться списать 10 раз по 10 u. = 100 u. всего
    sender_wallet, created = Wallet.objects.get_or_create(
        wallet_name='Test Sender Wallet',
        defaults={
            'balance': Decimal('100.00'),
        }
    )
    
    if not created:
        # Если кошелек уже существует, обновим баланс
        sender_wallet.balance = Decimal('100.00')
        sender_wallet.save()
        print(f"[OK] Обновлен кошелек отправителя: {sender_wallet.wallet_id}")
    else:
        print(f"[OK] Создан кошелек отправителя: {sender_wallet.wallet_id}")
    
    # Кошелек получателя
    receiver_wallet, created = Wallet.objects.get_or_create(
        wallet_name='Test Receiver Wallet',
        defaults={
            'balance': Decimal('0.00'),
        }
    )
    
    if not created:
        print(f"[OK] Кошелек получателя уже существует: {receiver_wallet.wallet_id}")
    else:
        print(f"[OK] Создан кошелек получателя: {receiver_wallet.wallet_id}")
    
    print(f"\n[*] Текущее состояние кошельков:")
    print(f"   Отправитель: {sender_wallet.wallet_name}")
    print(f"   ID: {sender_wallet.wallet_id}")
    print(f"   Баланс: {sender_wallet.balance} u.")
    print(f"\n   Получатель: {receiver_wallet.wallet_name}")
    print(f"   ID: {receiver_wallet.wallet_id}")
    print(f"   Баланс: {receiver_wallet.balance} u.")
    
    return sender_wallet, receiver_wallet


if __name__ == '__main__':
    print("=" * 60)
    print("Создание тестовых кошельков для проверки race condition")
    print("=" * 60)
    
    sender, receiver = create_test_wallets()
    
    print("\n" + "=" * 60)
    print("[OK] Готово! Можно запускать тест race condition.")
    print("=" * 60)

