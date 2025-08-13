from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Count, Prefetch
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

from .models import (
    SecDelModel, 
    SecDelMembers, 
    BackNForthChat
)
from api.sec_del_ser import (
    BackNForthChatSerializer,
    BackNForthChatCreateSerializer
)


class BackNForthChatPagination(PageNumberPagination):
    page_size = 5  # Reduced for easier testing
    page_size_query_param = 'page_size'
    max_page_size = 100


class BackNForthChatViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BackNForth chat messages in F-Links (SecDel)
    Provides CRUD operations and additional chat-related actions
    """
    serializer_class = BackNForthChatSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = BackNForthChatPagination
    
    def get_queryset(self):
        """Filter messages by F-Link and ensure user is a member"""
        try:
            sec_del_code = self.kwargs.get('sec_del_code')
            logger.info(f"Getting queryset for sec_del_code: {sec_del_code}")
            
            if not sec_del_code:
                logger.warning("No sec_del_code provided")
                return BackNForthChat.objects.none()
            
            try:
                sec_del = SecDelModel.objects.get(code=sec_del_code)
                logger.info(f"Found SecDel: {sec_del}")
            except SecDelModel.DoesNotExist:
                logger.error(f"SecDel with code {sec_del_code} not found")
                return BackNForthChat.objects.none()
            
            # Verify user is a member of the F-Link
            user = self.request.user
            logger.info(f"Checking membership for user: {user}")
            
            if not SecDelMembers.objects.filter(
                user=user,
                sec_del=sec_del,
                is_member=True
            ).exists():
                logger.warning(f"User {user} is not a member of SecDel {sec_del_code}")
                return BackNForthChat.objects.none()
            
            queryset = BackNForthChat.objects.filter(
                sec_del=sec_del,
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
            return BackNForthChat.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return BackNForthChatCreateSerializer
        return BackNForthChatSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['sec_del_code'] = self.kwargs.get('sec_del_code')
        return context
    
    def perform_create(self, serializer):
        """Create a new chat message"""
        sec_del_code = self.kwargs.get('sec_del_code')
        sec_del = get_object_or_404(SecDelModel, code=sec_del_code)
        
        # Verify user is a member
        if not SecDelMembers.objects.filter(
            user=self.request.user,
            sec_del=sec_del,
            is_member=True
        ).exists():
            raise permissions.PermissionDenied("You must be a F-Link member to send messages")
        
        serializer.save(sender=self.request.user, sec_del=sec_del)
    
    def destroy(self, request, *args, **kwargs):
        """Soft delete a message (only sender or delegate can delete)"""
        message = self.get_object()
        sec_del_code = self.kwargs.get('sec_del_code')
        sec_del = get_object_or_404(SecDelModel, code=sec_del_code)
        
        # Check if user is the sender or F-Link delegate
        is_sender = message.sender == request.user
        is_delegate = SecDelMembers.objects.filter(
            user=request.user,
            sec_del=sec_del,
            is_delegate=True
        ).exists()
        
        if not (is_sender or is_delegate):
            return Response(
                {"error": "You can only delete your own messages or if you're the F-Link delegate"},
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
    def search(self, request, sec_del_code=None):
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
    def statistics(self, request, sec_del_code=None):
        """Get chat statistics for the F-Link"""
        sec_del = get_object_or_404(SecDelModel, code=sec_del_code)
        
        # Total messages
        total_messages = BackNForthChat.objects.filter(
            sec_del=sec_del,
            is_deleted=False
        ).count()
        
        # Messages today
        today = timezone.now().date()
        messages_today = BackNForthChat.objects.filter(
            sec_del=sec_del,
            is_deleted=False,
            timestamp__date=today
        ).count()
        
        # Messages this week
        week_ago = timezone.now() - timedelta(days=7)
        messages_this_week = BackNForthChat.objects.filter(
            sec_del=sec_del,
            is_deleted=False,
            timestamp__gte=week_ago
        ).count()
        
        # Most active users
        active_users = BackNForthChat.objects.filter(
            sec_del=sec_del,
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
    def members_online(self, request, sec_del_code=None):
        """Get list of F-Link members (for chat participants display)"""
        sec_del = get_object_or_404(SecDelModel, code=sec_del_code)
        
        members = SecDelMembers.objects.filter(
            sec_del=sec_del,
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
