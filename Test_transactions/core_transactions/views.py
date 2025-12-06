import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import OperationalError
from .serializers import TransferSerializer, TransactionSerializer
from .models import Transaction
from .tasks import send_notification

COMMISSION_THRESHOLD = Decimal('1000.00')
COMMISSION_PERCENT = Decimal('0.10') 


class TransferView(APIView):
    def post(self, request):
        serializer = TransferSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        from_wallet_id = validated_data['from_wallet_id']
        to_wallet_id = validated_data['to_wallet_id']
        amount = validated_data['amount']
        commission = Decimal('0.00')
        if amount > COMMISSION_THRESHOLD:
            commission = (amount * COMMISSION_PERCENT).quantize(Decimal('0.01'))
        
        max_retries = 5
        retry_delay = 0.1 
        transaction_obj = None
        try:
            for attempt in range(max_retries):
                try:
                    transaction_obj = Transaction.create_transfer(
                        from_wallet_id=from_wallet_id,
                        to_wallet_id=to_wallet_id,
                        amount=amount,
                        commission=commission
                    )
                    break 
                    
                except OperationalError as e:
                    if 'database is locked' in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1)) 
                        continue 
                    else:
                        raise
            
            if transaction_obj:
                send_notification.delay(
                    transaction_id=str(transaction_obj.transaction_id),
                    to_wallet_id=str(to_wallet_id),
                    amount=str(amount),
                    commission=str(commission),
                )
                
                result_serializer = TransactionSerializer(transaction_obj)
                return Response(
                    {
                        'success': True,
                        'message': 'Перевод выполнен успешно',
                        'transaction': result_serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
            
        except ValueError as e:
            return Response(
                {
                    'success': False,
                    'message': str(e),
                    'error': 'INSUFFICIENT_FUNDS' if 'Недостаточно средств' in str(e) else 'VALIDATION_ERROR'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except ValidationError as e:
            return Response(
                {
                    'success': False,
                    'message': str(e),
                    'error': 'VALIDATION_ERROR'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            return Response(
                {
                    'success': False,
                    'message': f'Произошла ошибка при выполнении перевода: {str(e)}',
                    'error': 'INTERNAL_ERROR'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
