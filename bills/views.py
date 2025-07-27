from bills import models as billModels
from bills import serializers as billSerializers
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import PermissionDenied



class CustomPagination(PageNumberPagination):
    """
    We are creating a custome pagination for Bill and BillVote Model
    to limit the query and more """
    page_size = 10  # Number of items per page
    page_size_query_param = 'page_size'  # Allows the client to override the page size
    max_page_size = 100  # Maximum page size to prevent abuse

class BillViewSet(viewsets.ModelViewSet):
    """endpoints for Bills
    1. adding a new Bill,
    2. updating a bill record,
    3. removing a record.
     It handles the followings:
      1. pagination: default paginating is 10 and max is 100
      and can be changed via url param named: page_size
      2. it list bills.
      3. updates via put and patch request method.
      4. removed a record via delete request method"""

    queryset = billModels.Bill.objects.all()
    serializer_class = billSerializers.BillSerializer
    pagination_class = CustomPagination
    permission_classes = [AllowAny]


class BillVoteViewSet(viewsets.ModelViewSet):
    """We have bill vote view set in case that for sure there
    is going to be needed to have endpoints for
    1. adding a new vote,
    2. updating a vote record,
    3. removing a record.
     It handles the followings:
      1. pagination: default paginating is 10 and max is 100
      and can be changed via url param named: page_size
      2. it list the bill's votes.
      3. updates via put and patch request method.
      4. removed a record via delete request method"""
    queryset = billModels.BillVote.objects.all()
    serializer_class = billSerializers.BillVoteSerializer
    pagination_class = CustomPagination
    permission_classes = [AllowAny]


class BillUserNotesViewSet(viewsets.ModelViewSet):
    """ViewSet for BillUserNotes that allows users to:
    1. Create new notes for bills
    2. List their notes for bills
    3. Update existing notes
    4. Delete notes
    
    Features:
    - Pagination: default 10 items per page, max 100
    - Full CRUD operations
    - Users can only see and modify their own notes
    """
    queryset = billModels.BillUserNotes.objects.all()
    serializer_class = billSerializers.BillUserNotesSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter notes to show only the current user's notes for a specific bill"""
        queryset = billModels.BillUserNotes.objects.filter(user=self.request.user)
        
        # Filter by bill if bill_id is provided in query params
        bill_id = self.request.query_params.get('bill_id', None)
        if bill_id is not None:
            queryset = queryset.filter(bill_id=bill_id)
            
        return queryset

    def perform_create(self, serializer):
        """Automatically set the user when creating a note"""
        serializer.save(user=self.request.user)

class BillFirstDelNotesViewSet(viewsets.ModelViewSet):
    """ViewSet for BillFirstDelNotes that allows first delegates to:
    1. Create new notes for bills
    2. List first delegate notes for bills
    3. Update existing notes
    4. Delete notes
    
    Features:
    - Pagination: default 10 items per page, max 100
    - Full CRUD operations
    - Only first delegates can create/modify notes
    - All authenticated users can view first delegate notes
    """
    queryset = billModels.BillFirstDelNotes.objects.all()
    serializer_class = billSerializers.BillFirstDelNotesSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter notes based on user role and chain of delegation"""
        user = self.request.user
        
        # Filter by bill if bill_id is provided in query params
        bill_id = self.request.query_params.get('bill_id', None)
        
        # Check if user is a first delegate
        from vote.models import GroupMember
        is_first_delegate = GroupMember.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        # Build the queryset based on user role
        user_ids_to_show = []
        
        # Always include notes created by the current user
        user_ids_to_show.append(user.id)
        
        if not is_first_delegate:
            # If user is a regular member, find their first delegate from chain
            try:
                # Get the user's group membership
                group_member_instance = GroupMember.objects.filter(user=user).first()
                if group_member_instance:
                    # Find the first delegate in their group
                    f_del_instance = GroupMember.objects.filter(
                        group=group_member_instance.group,
                        is_delegate=True
                    ).first()
                    
                    if f_del_instance and f_del_instance.user.id not in user_ids_to_show:
                        # Add their first delegate's notes
                        user_ids_to_show.append(f_del_instance.user.id)
            except Exception as e:
                # If anything fails, just show user's own notes
                pass
        
        # Create the queryset
        queryset = billModels.BillFirstDelNotes.objects.filter(user_id__in=user_ids_to_show)
        
        # Filter by bill if bill_id is provided
        if bill_id is not None:
            queryset = queryset.filter(bill_id=bill_id)
            
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Automatically set the user when creating a note and validate first delegate status"""
        user = self.request.user
        
        # Check if the user is actually a first delegate by looking at GroupMember records
        from vote.models import GroupMember
        is_first_delegate = GroupMember.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_first_delegate:
            raise PermissionDenied("Only first delegates can create first delegate notes")
        serializer.save(user=user)

    def perform_update(self, serializer):
        """Only allow the creator of the note to update it"""
        user = self.request.user
        note_instance = self.get_object()
        
        # Check if the current user is the creator of the note
        if note_instance.user != user:
            raise PermissionDenied("You can only update notes that you created")
        
        # Also check if the user is still a first delegate
        from vote.models import GroupMember
        is_first_delegate = GroupMember.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_first_delegate:
            raise PermissionDenied("Only first delegates can update first delegate notes")
        
        serializer.save()

    def perform_destroy(self, instance):
        """Only allow the creator of the note to delete it"""
        user = self.request.user
        
        # Check if the current user is the creator of the note
        if instance.user != user:
            raise PermissionDenied("You can only delete notes that you created")
        
        # Also check if the user is still a first delegate
        from vote.models import GroupMember
        is_first_delegate = GroupMember.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_first_delegate:
            raise PermissionDenied("Only first delegates can delete first delegate notes")
        
        instance.delete()
