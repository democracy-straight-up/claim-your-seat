# Moda BackNForth Chat Implementation

## Overview

This implementation provides a complete BackNForth chat system for S-Links (Moda) in the DSUp application. The system allows S-Link members to communicate in real-time through WebSocket connections and provides RESTful API endpoints for chat management.

## Components Created

### 1. Database Model (`moda/models.py`)

- **ModaBackNForthChat**: New model added to handle chat messages for S-Links
  - Fields: moda, sender, message, reply_to, timestamp, is_edited, edited_at, is_deleted, deleted_at
  - Includes proper indexing for performance
  - Soft delete functionality

### 2. Serializers (`moda/serializers.py`)

- **ModaBackNForthChatSerializer**: For retrieving chat messages with full sender details
- **ModaBackNForthChatCreateSerializer**: For creating new chat messages
- Includes reply message handling and sender name resolution

### 3. WebSocket Consumer (`moda/backnforth_consumer.py`)

- **ModaBackNForthChatConsumer**: Handles real-time chat functionality
- Features:
  - User authentication and membership verification
  - Real-time message broadcasting
  - Message editing and deletion
  - User join/leave notifications
  - Proper error handling

### 4. API ViewSet (`moda/backnforth_views.py`)

- **ModaBackNForthChatViewSet**: RESTful API for chat management
- Endpoints:
  - `GET/POST /moda/backnforth/{moda_code}/messages/` - List and create messages
  - `GET/PUT/PATCH/DELETE /moda/backnforth/{moda_code}/messages/{id}/` - Message details
  - `GET /moda/backnforth/{moda_code}/messages/search/` - Search messages
  - `GET /moda/backnforth/{moda_code}/statistics/` - Chat statistics
  - `GET /moda/backnforth/{moda_code}/members/` - List members
- Includes pagination, search, and permission checking

### 5. URL Configuration (`moda/urls.py`)

- Added all necessary API endpoints for chat functionality
- Proper URL patterns for all chat operations

### 6. WebSocket Routing (`moda/routing.py`)

- **New file**: WebSocket URL patterns for Moda chat
- Route: `ws/moda/backnforth/{moda_code}/`

### 7. ASGI Configuration (`dsu/asgi.py`)

- Updated to include Moda WebSocket routing
- Maintains proper middleware stack

### 8. Database Migration

- Migration file created: `moda/migrations/0007_modabacknforthchat_and_more.py`
- Includes proper database indexes for performance

## Key Features

### Security & Permissions

- Only S-Link members can access chat
- Users can only edit/delete their own messages
- S-Link delegates can delete any message
- JWT token authentication for WebSocket connections

### Performance

- Proper database indexing
- Pagination for message listing
- Efficient querying with select_related

### User Experience

- Real-time messaging via WebSocket
- Message editing and deletion
- Reply-to functionality
- User join/leave notifications
- Chat statistics and search

## Technical Notes

### Simplified Implementation

As requested, the following features were **not** implemented to keep it simple:

- Typing indicators
- Read receipts
- Message reactions
- File attachments
- Advanced formatting

### WebSocket Message Format

```json
{
  "type": "chat_message",
  "message_data": {
    "id": 123,
    "message": "Hello world",
    "sender": {
      "id": 1,
      "username": "user123",
      "users": { "legalName": "John Doe" }
    },
    "sender_name": "John Doe",
    "timestamp": "2025-08-15T10:30:00Z",
    "reply_to_message": null,
    "is_edited": false,
    "edited_at": null
  }
}
```

### API Response Format

The REST API follows the same message format as the WebSocket implementation for consistency.

## Next Steps

### To Complete Implementation:

1. **Run Migration**: Execute the migration to create the database table
2. **Frontend Integration**: Create React components similar to the F-Link BackNForth chat
3. **Testing**: Test both WebSocket and REST API functionality
4. **Documentation**: Update API documentation

### Commands to Run:

```bash
# Apply the migration
python manage.py migrate moda

# Start the development server
python manage.py runserver
```

The system is now ready for frontend integration and testing!
