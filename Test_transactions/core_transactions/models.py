from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import uuid


class Wallet(models.Model):
    wallet_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID кошелька'
    )
    wallet_name = models.CharField(
        max_length=60,
        verbose_name='Название кошелька'
    )
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Баланс'
    )
    version = models.IntegerField(
        default=0,
        verbose_name='Версия'
    )
    is_admin = models.BooleanField(
        default=False,
        verbose_name='Технический кошелек'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Кошелек'
        verbose_name_plural = 'Кошельки'
        db_table = 'wallets'
        indexes = [
            models.Index(fields=['wallet_id']),
            models.Index(fields=['is_admin']),
        ]

    def __str__(self):
        return f"{self.wallet_name} ({self.wallet_id}) - {self.balance} u."

    @transaction.atomic
    def withdraw(self, amount: Decimal) -> bool:

        if amount <= 0:
            raise ValidationError("Сумма списания должна быть положительной")
        
  
        wallet = Wallet.objects.select_for_update(nowait=False).get(
            wallet_id=self.wallet_id
        )
        
        if wallet.balance < amount:
            return False
        
        wallet.balance -= amount
        wallet.version += 1
        wallet.save(update_fields=['balance', 'version', 'updated_at'])
        
        self.balance = wallet.balance
        self.version = wallet.version
        
        return True

    @transaction.atomic
    def deposit(self, amount: Decimal) -> None:
        if amount <= 0:
            raise ValidationError("Сумма зачисления должна быть положительной")
        
        wallet = Wallet.objects.select_for_update(nowait=False).get(
            wallet_id=self.wallet_id
        )
        
        wallet.balance += amount
        wallet.version += 1
        wallet.save(update_fields=['balance', 'version', 'updated_at'])
        
        self.balance = wallet.balance
        self.version = wallet.version

    @classmethod
    @transaction.atomic
    def get_admin_wallet(cls):
        admin_wallet, created = cls.objects.get_or_create(
            is_admin=True,
            defaults={
                'wallet_name': 'System Admin Wallet',
                'balance': Decimal('0.00'),
            }
        )
        return admin_wallet


class Transaction(models.Model):
    TRANSACTION_STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('completed', 'Завершена'),
        ('failed', 'Ошибка'),
        ('cancelled', 'Отменена'),
    ]

    transaction_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID транзакции'
    )
    from_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name='outgoing_transactions',
        verbose_name='Кошелек отправителя'
    )
    to_wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name='incoming_transactions',
        verbose_name='Кошелек получателя'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Сумма перевода'
    )
    commission = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name='Комиссия'
    )
    status = models.CharField(
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default='pending',
        verbose_name='Статус'
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        verbose_name='Сообщение об ошибке'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата завершения'
    )

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        db_table = 'transactions'
        indexes = [
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['from_wallet', 'to_wallet']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.amount} u. ({self.status})"

    def clean(self):
        if self.from_wallet_id == self.to_wallet_id:
            raise ValidationError("Кошелек отправителя и получателя не могут совпадать")
        
        if self.amount <= 0:
            raise ValidationError("Сумма перевода должна быть положительной")

    @classmethod
    @transaction.atomic
    def create_transfer(cls, from_wallet_id: uuid.UUID, to_wallet_id: uuid.UUID, amount: Decimal, commission: Decimal = Decimal('0.00')):
        if amount <= 0:
            raise ValidationError("Сумма перевода должна быть положительной")
        
        if commission < 0:
            raise ValidationError("Комиссия не может быть отрицательной")
        wallet_ids_to_lock = [from_wallet_id, to_wallet_id]
        admin_wallet_id = None
        if commission > 0:
            admin_wallet = Wallet.get_admin_wallet()
            admin_wallet_id = admin_wallet.wallet_id
            wallet_ids_to_lock.append(admin_wallet_id)

        wallets_dict = {
            wallet.wallet_id: wallet 
            for wallet in Wallet.objects.select_for_update().filter(
                wallet_id__in=wallet_ids_to_lock
            ).order_by('wallet_id')
        }
        
        if from_wallet_id not in wallets_dict:
            raise ValueError(f"Кошелек отправителя {from_wallet_id} не найден")
        
        if to_wallet_id not in wallets_dict:
            raise ValueError(f"Кошелек получателя {to_wallet_id} не найден")
        
        if commission > 0 and admin_wallet_id not in wallets_dict:
            raise ValueError(f"Административный кошелек {admin_wallet_id} не найден")
        
        from_wallet = wallets_dict[from_wallet_id]
        to_wallet = wallets_dict[to_wallet_id]
        
        if from_wallet.wallet_id == to_wallet.wallet_id:
            raise ValidationError("Кошелек отправителя и получателя не могут совпадать")
        
        total_debit = amount + commission
        if from_wallet.balance < total_debit:
            raise ValueError(
                f"Недостаточно средств. Требуется: {total_debit}, доступно: {from_wallet.balance}"
            )
        
        transaction_obj = cls.objects.create(
            from_wallet=from_wallet,
            to_wallet=to_wallet,
            amount=amount,
            commission=commission,
            status='pending'
        )
        
        try:
            from_wallet.balance -= total_debit
            from_wallet.version += 1
            from_wallet.save(update_fields=['balance', 'version', 'updated_at'])
            
            to_wallet.balance += amount
            to_wallet.version += 1
            to_wallet.save(update_fields=['balance', 'version', 'updated_at'])
            if commission > 0:
                admin_wallet = wallets_dict[admin_wallet_id]
                admin_wallet.balance += commission
                admin_wallet.version += 1
                admin_wallet.save(update_fields=['balance', 'version', 'updated_at'])
            
            transaction_obj.status = 'completed'
            transaction_obj.completed_at = timezone.now()
            transaction_obj.save(update_fields=['status', 'completed_at'])
            
            return transaction_obj
            
        except Exception as e:
            transaction_obj.status = 'failed'
            transaction_obj.error_message = str(e)
            transaction_obj.save(update_fields=['status', 'error_message'])
            raise

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
