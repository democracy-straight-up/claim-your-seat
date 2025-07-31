from bills import models as billModels
from bills import serializers as billSerializers
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
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

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def vote(self, request, pk=None):
        """Allow users to vote on a bill"""
        try:
            bill = self.get_object()
            your_vote = request.data.get('your_vote')
            
            print(f"Vote attempt: User={request.user.username}, Bill={bill.id}, Vote={your_vote}")
            
            if your_vote not in ['Y', 'N', 'Pr', 'Px']:
                print(f"Invalid vote value: {your_vote}")
                return Response(
                    {'error': 'Invalid vote. Must be Y, N, Pr, or Px'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if user has proper profile
            if not hasattr(request.user, 'users'):
                print(f"User {request.user.username} has no profile")
                return Response(
                    {'error': 'User profile not found'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get or create vote
            vote, created = billModels.BillVote.objects.get_or_create(
                bill=bill,
                voter=request.user,
                defaults={'your_vote': your_vote}
            )
            
            if not created:
                print(f"Updating existing vote from {vote.your_vote} to {your_vote}")
                # Update existing vote
                vote.your_vote = your_vote
                vote.save()
            else:
                print(f"Created new vote: {your_vote}")
            
            return Response({
                'message': 'Vote recorded successfully',
                'your_vote': vote.your_vote,
                'vote_display': vote.get_your_vote_display()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"Error in vote action: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Server error: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def my_vote(self, request, pk=None):
        """Get the current user's vote for this bill"""
        bill = self.get_object()
        try:
            vote = billModels.BillVote.objects.get(bill=bill, voter=request.user)
            return Response({
                'your_vote': vote.your_vote,
                'vote_display': vote.get_your_vote_display(),
                'vote_date': vote.vote_date
            })
        except billModels.BillVote.DoesNotExist:
            return Response({'your_vote': None})

    @action(detail=True, methods=['get'])
    def vote_counts(self, request, pk=None):
        """Get vote counts for this bill"""
        bill = self.get_object()
        print("here before", bill, request.user)
        
        # Get user's district for district counts
        user_district = None
        if request.user.is_authenticated:
            print("here", request.user)
            user_district = getattr(getattr(request.user, 'users', None), 'district', None)
            user_district_code = getattr(user_district, 'code', None) if user_district else None
        
        return Response({
            'national_counts': {
                'yea': bill.count_yea_votes(),
                'nay': bill.count_nay_votes(),
                'present': bill.count_present_votes(),
                'proxy': bill.count_proxy_votes()
            },
            'district_counts': {
                'yea': bill.count_district_yea_votes(user_district_code) if user_district_code else 0,
                'nay': bill.count_district_nay_votes(user_district_code) if user_district_code else 0,
                'present': bill.count_district_present_votes(user_district_code) if user_district_code else 0,
                'proxy': bill.count_district_proxy_votes(user_district_code) if user_district_code else 0
            } if user_district_code else {}
        })

class BillVoteViewSet(viewsets.ModelViewSet):
    """ViewSet for BillVote that allows users to:
    1. Create new votes for bills
    2. Update existing votes (no duplicates - will update existing vote)
    3. List votes
    4. Delete votes
     It handles the followings:
      1. pagination: default paginating is 10 and max is 100
      and can be changed via url param named: page_size
      2. it lists the bill's votes.
      3. updates via put and patch request method.
      4. removes a record via delete request method
      5. automatically handles vote updates instead of creating duplicates"""
    queryset = billModels.BillVote.objects.all()
    serializer_class = billSerializers.BillVoteSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter votes to show only user's own votes"""
        return billModels.BillVote.objects.filter(voter=self.request.user)

    def perform_create(self, serializer):
        """Create or update a vote - no duplicates allowed"""
        bill_id = serializer.validated_data.get('bill_id')
        user = self.request.user
        your_vote = serializer.validated_data.get('your_vote')
        
        # Try to get existing vote
        existing_vote, created = billModels.BillVote.objects.get_or_create(
            bill_id=bill_id,
            voter=user,
            defaults={'your_vote': your_vote}
        )
        
        if not created:
            # Update existing vote
            existing_vote.your_vote = your_vote
            existing_vote.save()
            
        return existing_vote

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

class BillHolcNotesViewSet(viewsets.ModelViewSet):
    """ViewSet for BillHolcNotes that allows Holc to:
    1. Create new notes for bills
    2. List Holc notes for bills
    3. Update existing notes
    4. Delete notes
    
    Features:
    - Pagination: default 10 items per page, max 100
    - Full CRUD operations
    - Only Holc can create/modify notes
    - All authenticated users can view Holc notes
    """
    queryset = billModels.BillHolcNotes.objects.all()
    serializer_class = billSerializers.BillHolcNotesSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter notes based on user role and chain of delegation"""
        user = self.request.user
        
        # Filter by bill if bill_id is provided in query params
        bill_id = self.request.query_params.get('bill_id', None)
        
        # Check if user is a Holc
        from holc.models import HolcMembers
        is_holc = HolcMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        # Build the queryset based on user role
        user_ids_to_show = []
        
        # Always include notes created by the current user
        user_ids_to_show.append(user.id)
        
        if not is_holc:
            # If user is a regular member, find their holc from chain
            try:
                # Get the user's Holc membership
                holc_member_instance = HolcMembers.objects.filter(user=user).first()
                if holc_member_instance:
                    # Find the Holc in their group
                    holc_delegate_instance = HolcMembers.objects.filter(
                        holc=holc_member_instance.holc,
                        is_delegate=True
                    ).first()
                    
                    if holc_delegate_instance and holc_delegate_instance.user.id not in user_ids_to_show:
                        # Add their Holc's notes
                        user_ids_to_show.append(holc_delegate_instance.user.id)
            except Exception as e:
                # If anything fails, just show user's own notes
                pass
        
        # Create the queryset
        queryset = billModels.BillHolcNotes.objects.filter(user_id__in=user_ids_to_show)
        
        # Filter by bill if bill_id is provided
        if bill_id is not None:
            queryset = queryset.filter(bill_id=bill_id)
            
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Automatically set the user when creating a note and validate Holc status"""
        user = self.request.user
        
        # Check if the user is actually a Holc by looking at HolcMembers records
        from holc.models import HolcMembers
        is_holc = HolcMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_holc:
            raise PermissionDenied("Only Holc can create Holc notes")
        serializer.save(user=user)

    def perform_update(self, serializer):
        """Only allow the creator of the note to update it"""
        user = self.request.user
        note_instance = self.get_object()
        
        # Check if the current user is the creator of the note
        if note_instance.user != user:
            raise PermissionDenied("You can only update notes that you created")
        
        # Also check if the user is still a Holc
        from holc.models import HolcMembers
        is_holc = HolcMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_holc:
            raise PermissionDenied("Only Holc can update Holc notes")
        
        serializer.save()

    def perform_destroy(self, instance):
        """Only allow the creator of the note to delete it"""
        user = self.request.user
        
        # Check if the current user is the creator of the note
        if instance.user != user:
            raise PermissionDenied("You can only delete notes that you created")
        
        # Also check if the user is still a MoDa
        from holc.models import HolcMembers
        is_holc = HolcMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_holc:
            raise PermissionDenied("Only Holc can delete Holc notes")
        
        instance.delete()

class BillHouseRepNotesViewSet(viewsets.ModelViewSet):
    """ViewSet for BillHouseRepNotes that allows House Rep to:
    1. Create new notes for bills
    2. List Holc notes for bills
    3. Update existing notes
    4. Delete notes
    
    Features:
    - Pagination: default 10 items per page, max 100
    - Full CRUD operations
    - Only Holc can create/modify notes
    - All authenticated users can view Holc notes
    """
    queryset = billModels.BillHouseRepNotes.objects.all()
    serializer_class = billSerializers.BillHouseRepNotesSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter notes based on user role and chain of delegation"""
        user = self.request.user

        # Filter by bill if bill_id is provided in query params
        bill_id = self.request.query_params.get('bill_id', None)
        
        # Check if user is a Holc
        from rep.models import DistrictCouncilMembers
        is_house_rep = DistrictCouncilMembers.objects.filter(user=user,is_delegate=True).exists()
        # Build the queryset based on user role
        user_ids_to_show = []
        # Always include notes created by the current user
        user_ids_to_show.append(user.id)
        
        if not is_house_rep:
            # If user is a regular member, find their holc from chain
            try:
                # Get the user's Holc membership
                rep_member_instance = DistrictCouncilMembers.objects.filter(user=user).first()
                if rep_member_instance:
                    # Find the Holc in their group
                    rep_delegate_instance = DistrictCouncilMembers.objects.filter(district_council=rep_member_instance.district_council, is_delegate=True).first()
                    if rep_delegate_instance and rep_delegate_instance.user.id not in user_ids_to_show:
                        # Add their Holc's notes
                        user_ids_to_show.append(rep_delegate_instance.user.id)
            except Exception as e:
                # If anything fails, just show user's own notes
                pass
        
        # Create the queryset
        queryset = billModels.BillHouseRepNotes.objects.filter(user_id__in=user_ids_to_show)

        # Filter by bill if bill_id is provided
        if bill_id is not None:
            queryset = queryset.filter(bill_id=bill_id)
            
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Automatically set the user when creating a note and validate House Rep status"""
        user = self.request.user
        # Check if the user is actually a Holc by looking at HolcMembers records
        from rep.models import DistrictCouncilMembers
        is_rep = DistrictCouncilMembers.objects.filter(user=user,is_delegate=True).exists()
        if not is_rep:
            raise PermissionDenied("Only House Rep can create House Rep notes")
        serializer.save(user=user)

    def perform_update(self, serializer):
        """Only allow the creator of the note to update it"""
        user = self.request.user
        note_instance = self.get_object()
        
        # Check if the current user is the creator of the note
        if note_instance.user != user:
            raise PermissionDenied("You can only update notes that you created")
        
        # Also check if the user is still a Holc
        from rep.models import DistrictCouncilMembers
        is_rep = DistrictCouncilMembers.objects.filter( user=user,is_delegate=True).exists()
        if not is_rep:
            raise PermissionDenied("Only House Rep can update House Rep notes")
        
        serializer.save()

    def perform_destroy(self, instance):
        """Only allow the creator of the note to delete it"""
        user = self.request.user
        
        # Check if the current user is the creator of the note
        if instance.user != user:
            raise PermissionDenied("You can only delete notes that you created")
        
        # Also check if the user is still a MoDa
        from rep.models import DistrictCouncilMembers
        is_rep = DistrictCouncilMembers.objects.filter(user=user,is_delegate=True).exists()
        
        if not is_rep:
            raise PermissionDenied("Only House Rep can delete House Rep notes")
        
        instance.delete()

class BillAdvisementViewSet(viewsets.ModelViewSet):
    """ViewSet for BillAdvisement that allows delegates to:
    1. Create new advisements for bills
    2. List advisements for bills
    3. Update existing advisements
    4. Delete advisements
    
    Features:
    - Pagination: default 10 items per page, max 100
    - Full CRUD operations
    - Only delegates can create/modify advisements based on their type
    - Users can view advisements from their delegates
    """
    queryset = billModels.BillAdvisement.objects.all()
    serializer_class = billSerializers.BillAdvisementSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter advisements based on user role and delegation chain"""
        user = self.request.user
        
        # Filter by bill if bill_id is provided in query params
        bill_id = self.request.query_params.get('bill_id', None)
        
        # Build the queryset based on user's delegation hierarchy
        user_delegate_ids = []
        
        try:
            # Check if user is a first delegate - get their advisements
            from vote.models import GroupMember
            if GroupMember.objects.filter(user=user, is_delegate=True).exists():
                user_delegate_ids.append(user.id)
            else:
                # If user is not a first delegate, find their first delegate
                group_member = GroupMember.objects.filter(user=user).first()
                if group_member:
                    f_del = GroupMember.objects.filter(
                        group=group_member.group,
                        is_delegate=True
                    ).first()
                    if f_del:
                        user_delegate_ids.append(f_del.user.id)
            
            # Check if user is a second delegate - get their advisements  
            from api.models import SecDelMembers
            if SecDelMembers.objects.filter(user=user, is_delegate=True).exists():
                user_delegate_ids.append(user.id)
            else:
                # If user is not a second delegate, find their second delegate
                sec_del_member = SecDelMembers.objects.filter(user=user).first()
                if sec_del_member:
                    sec_del = SecDelMembers.objects.filter(
                        sec_del=sec_del_member.sec_del,
                        is_delegate=True
                    ).first()
                    if sec_del:
                        user_delegate_ids.append(sec_del.user.id)
            
            # Check if user is a MoDa - get their advisements
            from moda.models import ModaMembers
            if ModaMembers.objects.filter(user=user, is_delegate=True).exists():
                user_delegate_ids.append(user.id)
            else:
                # If user is not a MoDa, find their MoDa
                moda_member = ModaMembers.objects.filter(user=user).first()
                if moda_member:
                    moda_del = ModaMembers.objects.filter(
                        moda=moda_member.moda,
                        is_delegate=True
                    ).first()
                    if moda_del:
                        user_delegate_ids.append(moda_del.user.id)
            
            # Check if user is a HoLC - get their advisements
            from holc.models import HolcMembers
            if HolcMembers.objects.filter(user=user, is_delegate=True).exists():
                user_delegate_ids.append(user.id)
            else:
                # If user is not a HoLC, find their HoLC
                holc_member = HolcMembers.objects.filter(user=user).first()
                if holc_member:
                    holc_del = HolcMembers.objects.filter(
                        holc=holc_member.holc,
                        is_delegate=True
                    ).first()
                    if holc_del:
                        user_delegate_ids.append(holc_del.user.id)
            
            # Check if user is a House Rep - get their advisements
            from rep.models import DistrictCouncilMembers
            if DistrictCouncilMembers.objects.filter(user=user, is_delegate=True).exists():
                user_delegate_ids.append(user.id)
            else:
                # If user is not a House Rep, find their House Rep
                rep_member = DistrictCouncilMembers.objects.filter(user=user).first()
                if rep_member:
                    rep_del = DistrictCouncilMembers.objects.filter(
                        district_council=rep_member.district_council,
                        is_delegate=True
                    ).first()
                    if rep_del:
                        user_delegate_ids.append(rep_del.user.id)
                        
        except Exception as e:
            # If anything fails, just show advisements by current user if they are a delegate
            pass
        
        # Create the queryset
        queryset = billModels.BillAdvisement.objects.filter(user_id__in=user_delegate_ids)
        
        # Filter by bill if bill_id is provided
        if bill_id is not None:
            queryset = queryset.filter(bill_id=bill_id)
            
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        """Automatically set the user when creating an advisement and validate delegate status"""
        user = self.request.user
        delegate_type = serializer.validated_data.get('type')
        
        # Additional validation that user can create this type of advisement
        if delegate_type == 'FD':
            from vote.models import GroupMember
            if not GroupMember.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only First Delegates can create FD advisements")
        elif delegate_type == 'SD':
            from api.models import SecDelMembers
            if not SecDelMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only Second Delegates can create SD advisements")
        elif delegate_type == 'MD':
            from moda.models import ModaMembers
            if not ModaMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only MoDa can create MD advisements")
        elif delegate_type == 'HL':
            from holc.models import HolcMembers
            if not HolcMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only HoLC can create HL advisements")
        elif delegate_type == 'HR':
            from rep.models import DistrictCouncilMembers
            if not DistrictCouncilMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only House Rep can create HR advisements")
        
        serializer.save(user=user)

    def perform_update(self, serializer):
        """Only allow the creator of the advisement to update it"""
        user = self.request.user
        advisement_instance = self.get_object()
        
        # Check if the current user is the creator of the advisement
        if advisement_instance.user != user:
            raise PermissionDenied("You can only update advisements that you created")
        
        # Validate user still has delegate status for the advisement type
        delegate_type = advisement_instance.type
        if delegate_type == 'FD':
            from vote.models import GroupMember
            if not GroupMember.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only First Delegates can update FD advisements")
        elif delegate_type == 'SD':
            from api.models import SecDelMembers
            if not SecDelMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only Second Delegates can update SD advisements")
        elif delegate_type == 'MD':
            from moda.models import ModaMembers
            if not ModaMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only MoDa can update MD advisements")
        elif delegate_type == 'HL':
            from holc.models import HolcMembers
            if not HolcMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only HoLC can update HL advisements")
        elif delegate_type == 'HR':
            from rep.models import DistrictCouncilMembers
            if not DistrictCouncilMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only House Rep can update HR advisements")
        
        serializer.save()

    def perform_destroy(self, instance):
        """Only allow the creator of the advisement to delete it"""
        user = self.request.user
        
        # Check if the current user is the creator of the advisement
        if instance.user != user:
            raise PermissionDenied("You can only delete advisements that you created")
        
        # Validate user still has delegate status for the advisement type
        delegate_type = instance.type
        if delegate_type == 'FD':
            from vote.models import GroupMember
            if not GroupMember.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only First Delegates can delete FD advisements")
        elif delegate_type == 'SD':
            from api.models import SecDelMembers
            if not SecDelMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only Second Delegates can delete SD advisements")
        elif delegate_type == 'MD':
            from moda.models import ModaMembers
            if not ModaMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only MoDa can delete MD advisements")
        elif delegate_type == 'HL':
            from holc.models import HolcMembers
            if not HolcMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only HoLC can delete HL advisements")
        elif delegate_type == 'HR':
            from rep.models import DistrictCouncilMembers
            if not DistrictCouncilMembers.objects.filter(user=user, is_delegate=True).exists():
                raise PermissionDenied("Only House Rep can delete HR advisements")
        
        instance.delete()
