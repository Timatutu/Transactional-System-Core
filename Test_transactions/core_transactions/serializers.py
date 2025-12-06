from rest_framework import serializers
from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import Wallet, Transaction
import uuid


class TransferSerializer(serializers.Serializer):
    from_wallet_id = serializers.UUIDField(
        help_text='ID кошелька отправителя'
    )
    to_wallet_id = serializers.UUIDField(
        help_text='ID кошелька получателя'
    )
    amount = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01'),
        help_text='Сумма перевода (минимум 0.01)'
    )

    def validate(self, data):
        from_wallet_id = data.get('from_wallet_id')
        to_wallet_id = data.get('to_wallet_id')
        amount = data.get('amount')

        if from_wallet_id == to_wallet_id:
            raise serializers.ValidationError({
                'to_wallet_id': 'Кошелек отправителя и получателя не могут совпадать.'
            })
        try:
            from_wallet = Wallet.objects.get(wallet_id=from_wallet_id)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError({
                'from_wallet_id': f'Кошелек с ID {from_wallet_id} не найден.'
            })

        try:
            to_wallet = Wallet.objects.get(wallet_id=to_wallet_id)
        except Wallet.DoesNotExist:
            raise serializers.ValidationError({
                'to_wallet_id': f'Кошелек с ID {to_wallet_id} не найден.'
            })

        if from_wallet.is_admin:
            raise serializers.ValidationError({
                'from_wallet_id': 'Нельзя переводить средства с технического кошелька.'
            })

        if amount <= 0:
            raise serializers.ValidationError({
                'amount': 'Сумма перевода должна быть положительной.'
            })

        return data


class TransactionSerializer(serializers.ModelSerializer):
    from_wallet_id = serializers.UUIDField(source='from_wallet.wallet_id', read_only=True)
    to_wallet_id = serializers.UUIDField(source='to_wallet.wallet_id', read_only=True)
    from_wallet_name = serializers.CharField(source='from_wallet.wallet_name', read_only=True)
    to_wallet_name = serializers.CharField(source='to_wallet.wallet_name', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'transaction_id',
            'from_wallet_id',
            'from_wallet_name',
            'to_wallet_id',
            'to_wallet_name',
            'amount',
            'commission',
            'status',
            'error_message',
            'created_at',
            'completed_at',
        ]
        read_only_fields = [
            'transaction_id',
            'commission',
            'status',
            'error_message',
            'created_at',
            'completed_at',
        ]