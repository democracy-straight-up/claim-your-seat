from django.urls import re_path
from moda import backnforth_consumer

websocket_urlpatterns = [
    re_path(r'ws/moda/backnforth/(?P<moda_code>\w+)/$',
        backnforth_consumer.ModaBackNForthChatConsumer.as_asgi()
    ),
]
