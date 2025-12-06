import time
import random
from celery import shared_task
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=3,
    autoretry_for=(Exception,),
    retry_backoff=False,
    retry_jitter=False,
)
def send_notification(self, transaction_id: str, to_wallet_id: str, amount: str, commission: str = "0.00"):
    try:
        logger.info(
            f"[Попытка {self.request.retries + 1}/4] "
            f"Отправка уведомления для транзакции {transaction_id}"
        )
        
        time.sleep(5)
        
        if random.random() < 0.3 and self.request.retries < 3:
            error_msg = f"Симуляция ошибки отправки уведомления (попытка {self.request.retries + 1})"
            logger.warning(error_msg)
            raise Exception(error_msg)
        
        message = (
            f"✅ Перевод получен!\n"
            f"Транзакция: {transaction_id}\n"
            f"Сумма: {amount} u.\n"
            f"Комиссия: {commission} u.\n"
            f"Ваш баланс пополнен."
        )
        
        logger.info(f"Уведомление успешно отправлено для транзакции {transaction_id}")
        logger.debug(f"Содержимое уведомления: {message}")
        
        return {
            'success': True,
            'transaction_id': transaction_id,
            'to_wallet_id': to_wallet_id,
            'message': message,
            'attempts': self.request.retries + 1,
        }
        
    except Exception as exc:
        logger.error(
            f"Ошибка при отправке уведомления для транзакции {transaction_id}: {str(exc)} "
            f"(попытка {self.request.retries + 1}/4)"
        )
        
        if self.request.retries < self.max_retries:
            logger.info(
                f"Перезапуск задачи через 3 секунды... "
                f"(осталось попыток: {self.max_retries - self.request.retries})"
            )
            raise self.retry(exc=exc, countdown=3)
        else:
            logger.error(
                f"Все попытки отправки уведомления исчерпаны для транзакции {transaction_id}. "
                f"Последняя ошибка: {str(exc)}"
            )
            return {
                'success': False,
                'transaction_id': transaction_id,
                'error': str(exc),
                'attempts': self.request.retries + 1,
                'message': 'Не удалось отправить уведомление после всех попыток',
            }

