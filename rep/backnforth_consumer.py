import json
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import DistrictCouncil, DistrictCouncilMembers, DistrictCouncilBackNForth


class DistrictCouncilBackNForthConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for BackNForth chat system in District Councils
    Handles real-time messaging for District Council members
    """
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.district_council_code = self.scope['url_route']['kwargs']['district_council_code']
        self.room_group_name = f'district_council_backnforth_chat_{self.district_council_code}'
        # Verify user is authenticated and is a member of the District Council
        if await self.is_user_member():
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            
            # Notify others that user joined
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'message': f'{self.scope["user"].username} joined the chat',
                    'user': self.scope["user"].username,
                    'status': 'joined'
                }
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
            elif message_type == 'edit_message':
                await self.handle_edit_message(text_data_json)
            elif message_type == 'delete_message':
                await self.handle_delete_message(text_data_json)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'error': 'Invalid JSON format'
            }))

    async def handle_chat_message(self, data):
        """Handle new chat message"""
        message_content = data.get('message', '').strip()
        reply_to_id = data.get('reply_to')
        
        if not message_content:
            await self.send(text_data=json.dumps({
                'error': 'Message cannot be empty'
            }))
            return
        
        # Save message to database
        message_data = await self.save_message(
            message_content, 
            reply_to_id
        )
        
        if message_data:
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message_broadcast',
                    'message_data': message_data
                }
            )

    async def handle_edit_message(self, data):
        """Handle message editing"""
        message_id = data.get('message_id')
        new_content = data.get('message', '').strip()
        
        if not new_content:
            await self.send(text_data=json.dumps({
                'error': 'Message cannot be empty'
            }))
            return
        
        success = await self.edit_message(message_id, new_content)
        
        if success:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'new_content': new_content,
                    'edited_by': self.scope["user"].username,
                    'edited_at': datetime.now().isoformat()
                }
            )

    async def handle_delete_message(self, data):
        """Handle message deletion"""
        message_id = data.get('message_id')
        
        success = await self.delete_message(message_id)
        
        if success:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_deleted',
                    'message_id': message_id,
                    'deleted_by': self.scope["user"].username,
                    'deleted_at': datetime.now().isoformat()
                }
            )

    # Broadcast message handlers
    async def chat_message_broadcast(self, event):
        """Send chat message to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message_data': event['message_data']
        }))

    async def message_edited(self, event):
        """Send message edit notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message_id': event['message_id'],
            'new_content': event['new_content'],
            'edited_by': event['edited_by'],
            'edited_at': event['edited_at']
        }))

    async def message_deleted(self, event):
        """Send message deletion notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': event['message_id'],
            'deleted_by': event['deleted_by'],
            'deleted_at': event['deleted_at']
        }))

    async def user_status(self, event):
        """Send user status notification to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'message': event['message'],
            'user': event['user'],
            'status': event['status']
        }))

    # Database operations
    @database_sync_to_async
    def is_user_member(self):
        """Check if user is a member of the District Council"""
        try:
            user = self.scope["user"]
            if user.is_anonymous:
                return False

            district_council = DistrictCouncil.objects.get(code=self.district_council_code)

            is_member = DistrictCouncilMembers.objects.filter(
                user=user,
                district_council=district_council,
                is_member=True
            ).exists()
            
            return is_member

        except DistrictCouncil.DoesNotExist:
            return False
        except Exception as e:
            return False

    @database_sync_to_async
    def save_message(self, message_content, reply_to_id=None):
        """Save message to database"""
        try:
            user = self.scope["user"]
            district_council = DistrictCouncil.objects.get(code=self.district_council_code)

            reply_to_message = None
            if reply_to_id:
                try:
                    reply_to_message = DistrictCouncilBackNForth.objects.get(
                        id=reply_to_id, 
                        district_council=district_council
                    )
                except DistrictCouncilBackNForth.DoesNotExist:
                    pass

            message = DistrictCouncilBackNForth.objects.create(
                district_council=district_council,
                sender=user,
                message=message_content,
                reply_to=reply_to_message
            )
            
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
                    'message': reply_to_message.message[:50] + '...' if len(reply_to_message.message) > 50 else reply_to_message.message,
                    'sender': reply_to_message.sender.username,
                    'sender_name': getattr(reply_to_message.sender.users, 'legalName', reply_to_message.sender.username)
                } if reply_to_message else None,
                'is_edited': message.is_edited,
                'edited_at': message.edited_at.isoformat() if message.edited_at else None
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None

    @database_sync_to_async
    def edit_message(self, message_id, new_content):
        """Edit an existing message"""
        try:
            user = self.scope["user"]
            district_council = DistrictCouncil.objects.get(code=self.district_council_code)

            message = DistrictCouncilBackNForth.objects.get(
                id=message_id,
                district_council=district_council,
                sender=user,
                is_deleted=False
            )
            
            message.message = new_content
            message.is_edited = True
            message.edited_at = datetime.now()
            message.save()
            
            return True

        except (DistrictCouncilBackNForth.DoesNotExist, Exception):
            return False

    @database_sync_to_async
    def delete_message(self, message_id):
        """Soft delete a message"""
        try:
            user = self.scope["user"]
            district_council = DistrictCouncil.objects.get(code=self.district_council_code)

            # Allow deletion by sender or District Council delegate
            is_delegate = DistrictCouncilMembers.objects.filter(
                user=user, 
                district_council=district_council, 
                is_delegate=True
            ).exists()
            
            if is_delegate:
                message = DistrictCouncilBackNForth.objects.get(
                    id=message_id,
                    district_council=district_council,
                    is_deleted=False
                )
            else:
                message = DistrictCouncilBackNForth.objects.get(
                    id=message_id,
                    district_council=district_council,
                    sender=user,
                    is_deleted=False
                )
            
            message.is_deleted = True
            message.deleted_at = datetime.now()
            message.save()
            
            return True

        except (DistrictCouncilBackNForth.DoesNotExist, Exception):
            return False
