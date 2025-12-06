from django.urls import path
from .views import TransferView

app_name = 'core_transactions'

urlpatterns = [
    path('transfer', TransferView.as_view(), name='transfer'),
]

