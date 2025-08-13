from django.urls import re_path
from api import backnforth_consumer

websocket_urlpatterns = [
    re_path(r'ws/backnforth/(?P<sec_del_code>\w+)/$',
        backnforth_consumer.BackNForthChatConsumer.as_asgi()
    ),
]
