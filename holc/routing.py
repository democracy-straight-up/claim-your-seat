from django.urls import re_path
from holc import backnforth_consumer

websocket_urlpatterns = [
    re_path(r'ws/holc/backnforth/(?P<holc_code>\w+)/$',
        backnforth_consumer.HolcBackNForthChatConsumer.as_asgi()
    ),
]
