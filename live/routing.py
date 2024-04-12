from django.urls import re_path
from live import consumers
from live import consumerCircle

websocket_urlpatterns = [
    re_path(r'ws/circle/(?P<circle_name>\w+)/(?P<user_name>\w+)/$',
            consumers.HouseKeepingConsumer.as_asgi()
        ),
    re_path(r'circle/(?P<circle_name>\w+)/(?P<user_name>\w+)',
            consumerCircle.CircleConsumer.as_asgi()
        ),
    re_path(r'ws/(?P<circleName>\w+)/(?P<userName>\w+)',
            consumers.CircleBackNForth.as_asgi()
        ),
]
