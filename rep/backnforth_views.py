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
    DistrictCouncil, 
    DistrictCouncilMembers, 
    DistrictCouncilBackNForth
)
from .serializers import (
    DistrictCouncilBackNForthSerializer,
    DistrictCouncilBackNForthCreateSerializer
)


class DistrictCouncilBackNForthPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 100


class DistrictCouncilBackNForthViewSet(viewsets.ModelViewSet):
    """
    ViewSet for BackNForth chat messages in district councils
    Provides CRUD operations and additional chat-related actions
    """
    serializer_class = DistrictCouncilBackNForthSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = DistrictCouncilBackNForthPagination
    
    def get_queryset(self):
        """Filter messages by District Council and ensure user is a member"""
        try:
            district_council_code = self.kwargs.get('district_council_code')
            logger.info(f"Getting queryset for district_council_code: {district_council_code}")

            if not district_council_code:
                logger.warning("No district_council_code provided")
                return DistrictCouncilBackNForth.objects.none()
            
            try:
                district_council = DistrictCouncil.objects.get(code=district_council_code)
                logger.info(f"Found District Council: {district_council}")
            except DistrictCouncil.DoesNotExist:
                logger.error(f"District Council with code {district_council_code} not found")
                return DistrictCouncilBackNForth.objects.none()

            # Verify user is a member of the District Council
            user = self.request.user
            logger.info(f"Checking membership for user: {user}")

            if not DistrictCouncilMembers.objects.filter(
                user=user,
                district_council=district_council,
                is_member=True
            ).exists():
                logger.warning(f"User {user} is not a member of District Council {district_council_code}")
                return DistrictCouncilBackNForth.objects.none()

            queryset = DistrictCouncilBackNForth.objects.filter(
                district_council=district_council,
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
            return DistrictCouncilBackNForth.objects.none()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DistrictCouncilBackNForthCreateSerializer
        return DistrictCouncilBackNForthSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['district_council_code'] = self.kwargs.get('district_council_code')
        return context
    
    def perform_create(self, serializer):
        """Create a new chat message"""
        district_council_code = self.kwargs.get('district_council_code')
        district_council = get_object_or_404(DistrictCouncil, code=district_council_code)

        # Verify user is a member
        if not DistrictCouncilMembers.objects.filter(
            user=self.request.user,
            district_council=district_council,
            is_member=True
        ).exists():
            raise permissions.PermissionDenied("You must be a District Council member to send messages")

        serializer.save(sender=self.request.user, district_council=district_council)

    def destroy(self, request, *args, **kwargs):
        """Soft delete a message (only sender or delegate can delete)"""
        message = self.get_object()
        district_council_code = self.kwargs.get('district_council_code')
        district_council = get_object_or_404(DistrictCouncil, code=district_council_code)

        # Check if user is the sender or District Council delegate
        is_sender = message.sender == request.user
        is_delegate = DistrictCouncilMembers.objects.filter(
            user=request.user,
            district_council=district_council,
            is_delegate=True
        ).exists()
        
        if not (is_sender or is_delegate):
            return Response(
                {"error": "You can only delete your own messages or if you're the District Council delegate"},
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
    def search(self, request, district_council_code=None):
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
    def statistics(self, request, district_council_code=None):
        """Get chat statistics for the District Council"""
        district_council = get_object_or_404(DistrictCouncil, code=district_council_code)

        # Total messages
        total_messages = DistrictCouncilBackNForth.objects.filter(
            district_council=district_council,
            is_deleted=False
        ).count()
        
        # Messages today
        today = timezone.now().date()
        messages_today = DistrictCouncilBackNForth.objects.filter(
            district_council=district_council,
            is_deleted=False,
            timestamp__date=today
        ).count()
        
        # Messages this week
        week_ago = timezone.now() - timedelta(days=7)
        messages_this_week = DistrictCouncilBackNForth.objects.filter(
            district_council=district_council,
            is_deleted=False,
            timestamp__gte=week_ago
        ).count()
        
        # Most active users
        active_users = DistrictCouncilBackNForth.objects.filter(
            district_council=district_council,
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
    def members_online(self, request, district_council_code=None):
        """Get list of District Council members (for chat participants display)"""
        district_council = get_object_or_404(DistrictCouncil, code=district_council_code)

        members = DistrictCouncilMembers.objects.filter(
            district_council=district_council,
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
