from django.urls import re_path
from bills import billConsumer

websocket_urlpatterns = [
    re_path(r'ws/bill/(?P<bill_id>\w+)/$',
        billConsumer.BillConsumer.as_asgi()
    ),
    re_path(r'ws/bill/(?P<bill_id>\w+)/(?P<circleName>\w+)/$',
        billConsumer.AdviceConsumer.as_asgi()
    ),

]
