from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

from .models import (
    HolcModel, 
    HolcMembers, 
    HolcBackNForthChat
)
from .serializers import (
    HolcBackNForthChatSerializer,
    HolcBackNForthChatCreateSerializer
)


class HolcBackNForthChatPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


class HolcBackNForthChatViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BackNForth chat messages in HoLC (House of Local Councils)
    Provides CRUD operations and additional chat-related actions
    """
    serializer_class = HolcBackNForthChatSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = HolcBackNForthChatPagination
    
    def get_queryset(self):
        """Filter messages by HoLC and ensure user is a member"""
        try:
            holc_code = self.kwargs.get('holc_code')
            logger.info(f"Getting queryset for holc_code: {holc_code}")
            
            if not holc_code:
                logger.warning("No holc_code provided")
                return HolcBackNForthChat.objects.none()
            
            try:
                holc = HolcModel.objects.get(code=holc_code)
                logger.info(f"Found HoLC: {holc}")
            except HolcModel.DoesNotExist:
                logger.error(f"HoLC with code {holc_code} not found")
                return HolcBackNForthChat.objects.none()
            
            # Verify user is a member of the HoLC
            user = self.request.user
            logger.info(f"Checking membership for user: {user}")
            
            if not HolcMembers.objects.filter(
                user=user,
                holc=holc,
                is_member=True
            ).exists():
                logger.warning(f"User {user} is not a member of HoLC {holc_code}")
                return HolcBackNForthChat.objects.none()
            
            queryset = HolcBackNForthChat.objects.filter(
                holc=holc,
                is_deleted=False
            ).select_related(
                'sender',
                'sender__users',
                'reply_to',
                'reply_to__sender'
            ).order_by('-timestamp')
            
            logger.info(f"Returning queryset with {queryset.count()} messages")
            return queryset
            
        except Exception as e:
            logger.error(f"Error in get_queryset: {str(e)}", exc_info=True)
            return HolcBackNForthChat.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return HolcBackNForthChatCreateSerializer
        return HolcBackNForthChatSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['holc_code'] = self.kwargs.get('holc_code')
        return context
    
    def perform_create(self, serializer):
        """Create a new chat message"""
        holc_code = self.kwargs.get('holc_code')
        holc = get_object_or_404(HolcModel, code=holc_code)
        
        # Verify user is a member
        if not HolcMembers.objects.filter(
            user=self.request.user,
            holc=holc,
            is_member=True
        ).exists():
            raise permissions.PermissionDenied("You must be a HoLC member to send messages")
        
        serializer.save(sender=self.request.user, holc=holc)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete a message (only sender or delegate can delete)"""
        message = self.get_object()
        holc_code = self.kwargs.get('holc_code')
        holc = get_object_or_404(HolcModel, code=holc_code)
        
        # Check if user is the sender or HoLC delegate
        is_sender = message.sender == request.user
        is_delegate = HolcMembers.objects.filter(
            user=request.user,
            holc=holc,
            is_delegate=True
        ).exists()
        
        if not (is_sender or is_delegate):
            return Response(
                {"error": "You can only delete your own messages or if you're the HoLC delegate"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Soft delete
        message.is_deleted = True
        message.deleted_at = timezone.now()
        message.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def update(self, request, *args, **kwargs):
        """Update a message (only sender can edit)"""
        message = self.get_object()
        
        if message.sender != request.user:
            return Response(
                {"error": "You can only edit your own messages"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update message content
        message.message = request.data.get('message', message.message)
        message.is_edited = True
        message.edited_at = timezone.now()
        message.save()
        
        serializer = self.get_serializer(message)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def search(self, request, holc_code=None):
        """Search messages by content"""
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return Response({'error': 'Search query is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        queryset = self.get_queryset().filter(
            Q(message__icontains=query)
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def statistics(self, request, holc_code=None):
        """Get chat statistics for the HoLC"""
        holc = get_object_or_404(HolcModel, code=holc_code)
        
        # Total messages
        total_messages = HolcBackNForthChat.objects.filter(
            holc=holc,
            is_deleted=False
        ).count()
        
        # Messages today
        today = timezone.now().date()
        messages_today = HolcBackNForthChat.objects.filter(
            holc=holc,
            is_deleted=False,
            timestamp__date=today
        ).count()
        
        # Messages this week
        week_ago = timezone.now() - timedelta(days=7)
        messages_this_week = HolcBackNForthChat.objects.filter(
            holc=holc,
            is_deleted=False,
            timestamp__gte=week_ago
        ).count()
        
        # Most active users
        active_users = HolcBackNForthChat.objects.filter(
            holc=holc,
            is_deleted=False,
            timestamp__gte=week_ago
        ).values(
            'sender__username',
            'sender__users__legalName'
        ).annotate(
            message_count=Count('id')
        ).order_by('-message_count')[:5]
        
        return Response({
            'total_messages': total_messages,
            'messages_today': messages_today,
            'messages_this_week': messages_this_week,
            'most_active_users': active_users
        })
    
    @action(detail=False, methods=['get'])
    def members_online(self, request, holc_code=None):
        """Get list of HoLC members (for chat participants display)"""
        holc = get_object_or_404(HolcModel, code=holc_code)
        
        members = HolcMembers.objects.filter(
            holc=holc,
            is_member=True
        ).select_related('user', 'user__users').order_by('user__username')
        
        members_data = []
        for member in members:
            members_data.append({
                'id': member.user.id,
                'username': member.user.username,
                'legal_name': getattr(member.user.users, 'legalName', member.user.username),
                'is_delegate': member.is_delegate,
                'joined_at': member.joined_at
            })
        
        return Response({'members': members_data})
