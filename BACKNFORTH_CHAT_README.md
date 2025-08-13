# BackNForth Chat System for F-Links (SecDel)

## Overview

The BackNForth chat system is a real-time messaging feature designed specifically for F-Links (Second Delegates) in the DSU (Democracy Straight Up) platform. This system allows F-Link members to communicate internally about their affairs using Django Channels with WebSocket protocol and Redis for real-time messaging.

## Features

### Core Features

- **Real-time messaging** using WebSockets
- **Message persistence** in PostgreSQL database
- **Message editing** (only by sender)
- **Message deletion** (soft delete by sender or F-Link delegate)
- **Reply to messages** functionality
- **Typing indicators**
- **Message search** functionality
- **Chat statistics**
- **Member list** for F-Link participants

### Security Features

- **Authentication required** - Only authenticated users can access
- **Membership verification** - Only F-Link members can participate in chat
- **Delegate privileges** - F-Link delegates can delete any message
- **Input validation** - All messages are validated before saving

## Architecture

### Models

#### BackNForthChat

```python
class BackNForthChat(models.Model):
    sec_del = models.ForeignKey(SecDelModel, on_delete=models.CASCADE, related_name='chat_messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
```

### WebSocket Consumer

The `BackNForthChatConsumer` handles real-time communication:

- **Connection Management**: Verifies user membership before allowing connection
- **Message Broadcasting**: Distributes messages to all connected F-Link members
- **Typing Indicators**: Shows when users are typing
- **User Status**: Notifies when users join/leave the chat

### API Endpoints

#### Chat Messages

- `GET /api/backnforth/{sec_del_code}/messages/` - List messages (paginated)
- `POST /api/backnforth/{sec_del_code}/messages/` - Send new message
- `GET /api/backnforth/{sec_del_code}/messages/{id}/` - Get specific message
- `PUT /api/backnforth/{sec_del_code}/messages/{id}/` - Edit message (sender only)
- `DELETE /api/backnforth/{sec_del_code}/messages/{id}/` - Delete message (sender or delegate)

#### Additional Features

- `GET /api/backnforth/{sec_del_code}/search/?q=query` - Search messages
- `GET /api/backnforth/{sec_del_code}/statistics/` - Get chat statistics
- `GET /api/backnforth/{sec_del_code}/members/` - List F-Link members

### WebSocket Endpoints

- `ws://domain/ws/backnforth/{sec_del_code}/` - WebSocket connection for real-time chat

## Usage

### Backend Setup

1. **Models are already created** in `api/models.py`
2. **Consumer** is implemented in `api/backnforth_consumer.py`
3. **Views** are available in `api/backnforth_views.py`
4. **Routing** is configured in `api/routing.py`

### WebSocket Message Types

#### Sending Messages

```javascript
// Send a new message
websocket.send(
  JSON.stringify({
    type: "chat_message",
    message: "Hello everyone!",
    reply_to: null, // optional: ID of message to reply to
  })
);
```

#### Editing Messages

```javascript
// Edit an existing message
websocket.send(
  JSON.stringify({
    type: "edit_message",
    message_id: 123,
    message: "Updated message content",
  })
);
```

#### Deleting Messages

```javascript
// Delete a message
websocket.send(
  JSON.stringify({
    type: "delete_message",
    message_id: 123,
  })
);
```

#### Typing Indicators

```javascript
// Show typing indicator
websocket.send(
  JSON.stringify({
    type: "typing",
    is_typing: true,
  })
);

// Hide typing indicator
websocket.send(
  JSON.stringify({
    type: "typing",
    is_typing: false,
  })
);
```

### Received Message Types

#### New Message

```javascript
{
    type: 'chat_message',
    message_data: {
        id: 123,
        message: 'Hello everyone!',
        sender: 'user123',
        sender_name: 'John Doe',
        timestamp: '2025-08-13T10:30:00Z',
        reply_to: null,
        is_edited: false,
        edited_at: null
    }
}
```

#### Message Edited

```javascript
{
    type: 'message_edited',
    message_id: 123,
    new_content: 'Updated message',
    edited_by: 'user123',
    edited_at: '2025-08-13T10:35:00Z'
}
```

#### Message Deleted

```javascript
{
    type: 'message_deleted',
    message_id: 123,
    deleted_by: 'user123',
    deleted_at: '2025-08-13T10:40:00Z'
}
```

#### User Status

```javascript
{
    type: 'user_status',
    message: 'user123 joined the chat',
    user: 'user123',
    status: 'joined' // or 'left'
}
```

#### Typing Status

```javascript
{
    type: 'typing_status',
    user: 'user123',
    is_typing: true
}
```

## Frontend Integration

### JavaScript Example

```javascript
class BackNForthChat {
  constructor(secDelCode, token) {
    this.secDelCode = secDelCode;
    this.token = token;
    this.websocket = null;
    this.connect();
  }

  connect() {
    const wsUrl = `ws://localhost:8000/ws/backnforth/${this.secDelCode}/`;
    this.websocket = new WebSocket(wsUrl);

    this.websocket.onopen = (event) => {
      console.log("Connected to BackNForth chat");
    };

    this.websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMessage(data);
    };

    this.websocket.onclose = (event) => {
      console.log("Disconnected from chat");
    };
  }

  handleMessage(data) {
    switch (data.type) {
      case "chat_message":
        this.displayMessage(data.message_data);
        break;
      case "message_edited":
        this.updateMessage(data.message_id, data.new_content);
        break;
      case "message_deleted":
        this.removeMessage(data.message_id);
        break;
      case "user_status":
        this.showUserStatus(data.message);
        break;
      case "typing_status":
        this.showTypingIndicator(data.user, data.is_typing);
        break;
      case "recent_messages":
        this.loadMessages(data.messages);
        break;
    }
  }

  sendMessage(message, replyTo = null) {
    this.websocket.send(
      JSON.stringify({
        type: "chat_message",
        message: message,
        reply_to: replyTo,
      })
    );
  }

  editMessage(messageId, newContent) {
    this.websocket.send(
      JSON.stringify({
        type: "edit_message",
        message_id: messageId,
        message: newContent,
      })
    );
  }

  deleteMessage(messageId) {
    this.websocket.send(
      JSON.stringify({
        type: "delete_message",
        message_id: messageId,
      })
    );
  }

  showTyping(isTyping) {
    this.websocket.send(
      JSON.stringify({
        type: "typing",
        is_typing: isTyping,
      })
    );
  }

  // Implementation methods for UI updates
  displayMessage(messageData) {
    // Add message to chat UI
  }

  updateMessage(messageId, newContent) {
    // Update message in chat UI
  }

  removeMessage(messageId) {
    // Remove message from chat UI
  }

  showUserStatus(message) {
    // Show user join/leave notification
  }

  showTypingIndicator(user, isTyping) {
    // Show/hide typing indicator
  }

  loadMessages(messages) {
    // Load initial messages
  }
}

// Usage
const chat = new BackNForthChat("1234", "auth-token");
```

## Database Migration

To create the database tables, run:

```bash
cd /path/to/claim-your-seat
python manage.py makemigrations api
python manage.py migrate
```

## Testing

### Manual Testing

1. **Create F-Link members** using the existing SecDel system
2. **Connect to WebSocket** using the F-Link code
3. **Send messages** and verify real-time delivery
4. **Test editing** and deletion functionality
5. **Verify permissions** (only members can access, only delegates can delete others' messages)

### API Testing

```bash
# List messages
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/backnforth/1234/messages/

# Send message
curl -X POST \
     -H "Authorization: Bearer <token>" \
     -H "Content-Type: application/json" \
     -d '{"message": "Hello from API!"}' \
     http://localhost:8000/api/backnforth/1234/messages/

# Search messages
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/backnforth/1234/search/?q=hello

# Get statistics
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/backnforth/1234/statistics/
```

## Security Considerations

1. **Authentication**: All endpoints require valid JWT tokens
2. **Authorization**: Only F-Link members can access their chat
3. **Input Validation**: Messages are validated for content and length
4. **Rate Limiting**: Consider implementing rate limiting for message sending
5. **Content Filtering**: Consider adding profanity filters if needed

## Performance Considerations

1. **Pagination**: Messages are paginated (50 per page by default)
2. **Database Indexing**: Indexes on `sec_del`, `timestamp`, and `is_deleted` fields
3. **Redis Caching**: Redis is used for WebSocket channel management
4. **Query Optimization**: Select_related and prefetch_related used for efficient queries

## Future Enhancements

1. **File Attachments**: Add support for file/image sharing
2. **Message Reactions**: Add emoji reactions to messages
3. **Push Notifications**: Notify offline users of new messages
4. **Message Threading**: Nested reply functionality
5. **Message Encryption**: End-to-end encryption for sensitive communications
6. **Voice Messages**: Audio message support
7. **Message Export**: Export chat history functionality

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**

   - Check if Redis is running
   - Verify ASGI configuration
   - Ensure user is authenticated

2. **Messages Not Persisting**

   - Check database connection
   - Verify model migrations are applied
   - Check user permissions

3. **Real-time Updates Not Working**
   - Verify WebSocket connection
   - Check Redis connection
   - Ensure channel layer configuration

### Debugging

Enable Django logging to debug issues:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'api.backnforth_consumer': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```
