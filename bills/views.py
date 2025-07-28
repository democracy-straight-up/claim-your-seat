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

class BillSecondDelNotesViewSet(viewsets.ModelViewSet):
    """ViewSet for BillSecondDelNotes that allows second delegates to:
    1. Create new notes for bills
    2. List second delegate notes for bills
    3. Update existing notes
    4. Delete notes
    
    Features:
    - Pagination: default 10 items per page, max 100
    - Full CRUD operations
    - Only second delegates can create/modify notes
    - All authenticated users can view second delegate notes
    """
    queryset = billModels.BillSecondDelNotes.objects.all()
    serializer_class = billSerializers.BillSecondDelNotesSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter notes based on user role and chain of delegation"""
        user = self.request.user
        
        # Filter by bill if bill_id is provided in query params
        bill_id = self.request.query_params.get('bill_id', None)
        
        # Check if user is a second delegate
        from api.models import SecDelMembers
        is_second_delegate = SecDelMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        # Build the queryset based on user role
        user_ids_to_show = []
        
        # Always include notes created by the current user
        user_ids_to_show.append(user.id)
        
        if not is_second_delegate:
            # If user is a regular member, find their second delegate from chain
            try:
                # Get the user's second delegate membership
                sec_del_member_instance = SecDelMembers.objects.filter(user=user).first()
                if sec_del_member_instance:
                    # Find the second delegate in their group
                    sec_del_delegate_instance = SecDelMembers.objects.filter(
                        sec_del=sec_del_member_instance.sec_del,
                        is_delegate=True
                    ).first()
                    
                    if sec_del_delegate_instance and sec_del_delegate_instance.user.id not in user_ids_to_show:
                        # Add their second delegate's notes
                        user_ids_to_show.append(sec_del_delegate_instance.user.id)
            except Exception as e:
                # If anything fails, just show user's own notes
                pass
        
        # Create the queryset
        queryset = billModels.BillSecondDelNotes.objects.filter(user_id__in=user_ids_to_show)
        
        # Filter by bill if bill_id is provided
        if bill_id is not None:
            queryset = queryset.filter(bill_id=bill_id)
            
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Automatically set the user when creating a note and validate second delegate status"""
        user = self.request.user
        
        # Check if the user is actually a second delegate by looking at SecDelMembers records
        from api.models import SecDelMembers
        is_second_delegate = SecDelMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_second_delegate:
            raise PermissionDenied("Only second delegates can create second delegate notes")
        serializer.save(user=user)

    def perform_update(self, serializer):
        """Only allow the creator of the note to update it"""
        user = self.request.user
        note_instance = self.get_object()
        
        # Check if the current user is the creator of the note
        if note_instance.user != user:
            raise PermissionDenied("You can only update notes that you created")
        
        # Also check if the user is still a second delegate
        from api.models import SecDelMembers
        is_second_delegate = SecDelMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_second_delegate:
            raise PermissionDenied("Only second delegates can update second delegate notes")
        
        serializer.save()

    def perform_destroy(self, instance):
        """Only allow the creator of the note to delete it"""
        user = self.request.user
        
        # Check if the current user is the creator of the note
        if instance.user != user:
            raise PermissionDenied("You can only delete notes that you created")
        
        # Also check if the user is still a second delegate
        from api.models import SecDelMembers
        is_second_delegate = SecDelMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_second_delegate:
            raise PermissionDenied("Only second delegates can delete second delegate notes")
        
        instance.delete()


class BillModaNotesViewSet(viewsets.ModelViewSet):
    """ViewSet for BillModaNotes that allows MoDa to:
    1. Create new notes for bills
    2. List MoDa notes for bills
    3. Update existing notes
    4. Delete notes
    
    Features:
    - Pagination: default 10 items per page, max 100
    - Full CRUD operations
    - Only MoDa can create/modify notes
    - All authenticated users can view MoDa notes
    """
    queryset = billModels.BillModaNotes.objects.all()
    serializer_class = billSerializers.BillModaNotesSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter notes based on user role and chain of delegation"""
        user = self.request.user
        
        # Filter by bill if bill_id is provided in query params
        bill_id = self.request.query_params.get('bill_id', None)
        
        # Check if user is a MoDa
        from moda.models import ModaMembers
        is_moda = ModaMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        # Build the queryset based on user role
        user_ids_to_show = []
        
        # Always include notes created by the current user
        user_ids_to_show.append(user.id)
        
        if not is_moda:
            # If user is a regular member, find their MoDa from chain
            try:
                # Get the user's MoDa membership
                moda_member_instance = ModaMembers.objects.filter(user=user).first()
                if moda_member_instance:
                    # Find the MoDa in their group
                    moda_delegate_instance = ModaMembers.objects.filter(
                        moda=moda_member_instance.moda,
                        is_delegate=True
                    ).first()
                    
                    if moda_delegate_instance and moda_delegate_instance.user.id not in user_ids_to_show:
                        # Add their MoDa's notes
                        user_ids_to_show.append(moda_delegate_instance.user.id)
            except Exception as e:
                # If anything fails, just show user's own notes
                pass
        
        # Create the queryset
        queryset = billModels.BillModaNotes.objects.filter(user_id__in=user_ids_to_show)
        
        # Filter by bill if bill_id is provided
        if bill_id is not None:
            queryset = queryset.filter(bill_id=bill_id)
            
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Automatically set the user when creating a note and validate MoDa status"""
        user = self.request.user
        
        # Check if the user is actually a MoDa by looking at ModaMembers records
        from moda.models import ModaMembers
        is_moda = ModaMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_moda:
            raise PermissionDenied("Only MoDa can create MoDa notes")
        serializer.save(user=user)

    def perform_update(self, serializer):
        """Only allow the creator of the note to update it"""
        user = self.request.user
        note_instance = self.get_object()
        
        # Check if the current user is the creator of the note
        if note_instance.user != user:
            raise PermissionDenied("You can only update notes that you created")
        
        # Also check if the user is still a MoDa
        from moda.models import ModaMembers
        is_moda = ModaMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_moda:
            raise PermissionDenied("Only MoDa can update MoDa notes")
        
        serializer.save()

    def perform_destroy(self, instance):
        """Only allow the creator of the note to delete it"""
        user = self.request.user
        
        # Check if the current user is the creator of the note
        if instance.user != user:
            raise PermissionDenied("You can only delete notes that you created")
        
        # Also check if the user is still a MoDa
        from moda.models import ModaMembers
        is_moda = ModaMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_moda:
            raise PermissionDenied("Only MoDa can delete MoDa notes")
        
        instance.delete()
