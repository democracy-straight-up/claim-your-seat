import pytest
from dsu.asgi import application
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from .models import Bill, BillVote
from django.contrib.auth.models import User

TEST_CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

@database_sync_to_async
def create_user():
    user = User.objects.create_user(username='test',
                                 email='test@test.com',
                                 password='test')

@database_sync_to_async
def create_bill():
    bill = Bill.objects.create()

@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestWebSocket:
    async def test_consumer_create(self, settings):
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        _, access = await create_user()
        communicator = WebsocketCommunicator(application, "/ws/bill/6127/")
        connected, subprotocol = await communicator.connect()
        assert connected
        # Test sending text
        message={
            "vote_type":"N",
            "username":"test"
        }
        # channel_layer = get_channel_layer()
        # await channel_layer.group_send('test', message=message)
        await communicator.send_json_to(message)
        response = await communicator.receive_json_from()
        print(response)
        # Close
        await communicator.disconnect()

    async def test_consumer_update(self, settings):
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        communicator = WebsocketCommunicator(application, "/ws/bill/6127/")
        connected, subprotocol = await communicator.connect()
        assert connected
        # Test sending text
        await communicator.send_json_to({"vote_type":"N","username":"B5B3L"})
        response = await communicator.receive_json_from()
        print(response)
        # Close
        await communicator.disconnect()

    async def test_consumer_no_bill(self, settings):
        settings.CHANNEL_LAYERS = TEST_CHANNEL_LAYERS
        communicator = WebsocketCommunicator(application, "/ws/bill/6127/")
        connected, subprotocol = await communicator.connect()
        assert connected
        # Test sending text
        await communicator.send_json_to({"vote_type":"N","username":"B5B3L"})
        response = await communicator.receive_json_from()
        print(response)
        # Close
        await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db
async def test_get_bill():
    billobj = await database_sync_to_async(Bill.objects.get)(number="6127")
    print(billobj)

@pytest.mark.django_db
def test_get_data():
    billobj = Bill.objects.get(number="6127")
    print(billobj)
