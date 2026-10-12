import json
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import SecDelModel, SecDelMembers, BackNForthChat


class BackNForthChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for BackNForth chat system in F-Links (SecDel)
    Handles real-time messaging for F-Link members
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.sec_del_code = self.scope['url_route']['kwargs']['sec_del_code']
        self.room_group_name = f'backnforth_chat_{self.sec_del_code}'
        
        # Verify user is authenticated and is a member of the F-Link
        if await self.is_user_member():
            # Join room group
            await self.channel_layer.group_add(self.room_group_name,self.channel_name)
            await self.accept()
            
            # Don't send recent messages - let the frontend handle pagination via REST API
            # await self.send_recent_messages()
            
            # Notify others that user joined
            await self.channel_layer.group_send(
                self.room_group_name,
                { 'type': 'user_status',
                    'message': f'{self.scope["user"].username} joined the chat',
                    'user': self.scope["user"].username,
                    'status': 'joined' }
            )
        else:
            await self.close()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        # Notify others that user left
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'message': f'{self.scope["user"].username} left the chat',
                    'user': self.scope["user"].username,
                    'status': 'left'
                }
            )
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """Handle received WebSocket messages"""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'chat_message')
            
            if message_type == 'chat_message':
                await self.handle_chat_message(text_data_json)
            elif message_type == 'typing':
                await self.handle_typing(text_data_json)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))

    async def handle_chat_message(self, data):
        """Handle new chat message"""
        message_content = data.get('message', '').strip()
        reply_to_id = data.get('reply_to')
        
        if not message_content:
            await self.send(text_data=json.dumps({'error': 'Message cannot be empty'}))
            return
        
        # Save message to database
        message_data = await self.save_message( message_content, reply_to_id)
        
        if message_data:
            # Send message to room group
            await self.channel_layer.group_send(self.room_group_name,{'type':'chat_message_broadcast','message_data': message_data})

    async def handle_typing(self, data):
        """Handle typing indicator"""
        is_typing = data.get('is_typing', False)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_status',
                'user': self.scope["user"].username,
                'is_typing': is_typing
            }
        )

    # Broadcast message handlers
    async def chat_message_broadcast(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({'type': 'chat_message','message_data': event['message_data']}))

    async def user_status(self, event):
        """Send user status notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'message': event['message'],
            'user': event['user'],
            'status': event['status']
        }))

    async def typing_status(self, event):
        """Send typing status to WebSocket"""
        # Don't send typing status to the user who is typing
        if event['user'] != self.scope["user"].username:
            await self.send(text_data=json.dumps({
                'type': 'typing_status',
                'user': event['user'],
                'is_typing': event['is_typing']
            }))

    # Database operations
    @database_sync_to_async
    def is_user_member(self):
        """Check if user is a member of the F-Link"""
        try:
            user = self.scope["user"]
            if user.is_anonymous:
                return False
            sec_del = SecDelModel.objects.get(code=self.sec_del_code)
            is_member = SecDelMembers.objects.filter( user=user, sec_del=sec_del, is_member=True).exists()
            return is_member
        except SecDelModel.DoesNotExist:
            return False
        except Exception as e:
            return False

    @database_sync_to_async
    def save_message(self, message_content, reply_to_id=None):
        """Save message to database"""
        try:
            user = self.scope["user"]
            sec_del = SecDelModel.objects.get(code=self.sec_del_code)
            reply_to_message = None
            if reply_to_id:
                try:
                    reply_to_message = BackNForthChat.objects.get(id=reply_to_id, sec_del=sec_del)
                except BackNForthChat.DoesNotExist:
                    pass
            message = BackNForthChat.objects.create( sec_del=sec_del,sender=user, message=message_content,reply_to=reply_to_message)
            # Return serialized message data
            return {
                'id': message.id,
                'message': message.message,
                'sender': {
                    'id': message.sender.id,
                    'username': message.sender.username,
                    'email': message.sender.email,
                    'date_joined': message.sender.date_joined.isoformat(),
                    'users': {
                        'legalName': getattr(message.sender.users, 'legalName', message.sender.username)
                    }
                },
                'sender_name': getattr(message.sender.users, 'legalName', message.sender.username),
                'timestamp': message.timestamp.isoformat(),
                'reply_to_message': {
                    'id': reply_to_message.id,
                    'message': (
                        reply_to_message.message[:50] + '...'
                        if len(reply_to_message.message) > 50
                        else reply_to_message.message
                    ),
                    'sender': (
                        reply_to_message.sender.username
                        if reply_to_message.sender
                        else None
                    ),
                    'sender_name': (
                        getattr(
                            reply_to_message.sender.users,
                            'legalName',
                            reply_to_message.sender.username,
                        )
                        if reply_to_message.sender
                        else 'System'
                    ),
                } if reply_to_message else None,
                'is_edited': message.is_edited,
                'edited_at': message.edited_at.isoformat() if message.edited_at else None
            }
            
        except Exception as e:
            print(f"Error saving message: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    @database_sync_to_async
    def get_recent_messages(self, limit=50):
        """Get recent messages from the F-Link chat"""
        try:
            sec_del = SecDelModel.objects.get(code=self.sec_del_code)
            messages = BackNForthChat.objects.filter(sec_del=sec_del,is_deleted=False ).select_related('sender', 'reply_to').order_by('-timestamp')[:limit]
            
            message_list = []
            for message in reversed(messages):
                sender = message.sender
                reply_sender = (
                    message.reply_to.sender
                    if message.reply_to
                    else None
                )

                message_data = {
                    'id': message.id,
                    'message': message.message,
                    'sender': {
                        'id': sender.id,
                        'username': sender.username,
                        'email': sender.email,
                        'date_joined': sender.date_joined.isoformat(),
                        'users': {
                            'legalName': getattr(
                                sender.users,
                                'legalName',
                                sender.username,
                            )
                        },
                    } if sender else None,
                    'sender_name': (
                        getattr(
                            sender.users,
                            'legalName',
                            sender.username,
                        )
                        if sender
                        else 'System'
                    ),
                    'timestamp': message.timestamp.isoformat(),
                    'reply_to_message': {
                        'id': message.reply_to.id,
                        'message': (
                            message.reply_to.message[:50] + '...'
                            if len(message.reply_to.message) > 50
                            else message.reply_to.message
                        ),
                        'sender': (
                            reply_sender.username
                            if reply_sender
                            else None
                        ),
                        'sender_name': (
                            getattr(
                                reply_sender.users,
                                'legalName',
                                reply_sender.username,
                            )
                            if reply_sender
                            else 'System'
                        ),
                    } if message.reply_to else None,
                    'is_edited': message.is_edited,
                    'edited_at': (
                        message.edited_at.isoformat()
                        if message.edited_at
                        else None
                    ),
                    'is_system': message.is_system,
                }
                message_list.append(message_data)
            
            return message_list
            
        except Exception as e:
            print(f"Error getting recent messages: {str(e)}")
            return []

    async def send_recent_messages(self):
        """Send recent messages to newly connected user"""
        messages = await self.get_recent_messages()
        if messages:
            await self.send(text_data=json.dumps({
                'type': 'recent_messages',
                'messages': messages
            }))
