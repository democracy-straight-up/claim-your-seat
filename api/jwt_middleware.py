from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()


class JWTAuthMiddleware:
    """
    Custom JWT auth middleware for Django Channels WebSocket connections.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # Get token from query string
        query_string = parse_qs(scope.get('query_string', b'').decode())
        token = query_string.get('token', [None])[0]

        if token:
            try:
                # Validate token and get user
                user = await self.get_user_from_token(token)
                scope['user'] = user
            except Exception as e:
                print(f"JWT Authentication error: {e}")
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()

        return await self.inner(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            # Validate the token
            access_token = AccessToken(token)
            
            # Get user from token
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)
            
            return user
        except (InvalidToken, TokenError, User.DoesNotExist) as e:
            raise Exception(f"Invalid token or user: {e}")
