from django.urls import re_path
from rep import backnforth_consumer

websocket_urlpatterns = [
    re_path(r'ws/rep/backnforth/(?P<district_council_code>\w+)/$',
        backnforth_consumer.DistrictCouncilBackNForthConsumer.as_asgi()
    ),
]
