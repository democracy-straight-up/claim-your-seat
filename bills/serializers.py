from rest_framework import serializers
from bills import models as billModels
from django.contrib.auth.models import User
from rest_framework.reverse import reverse

class BillSerializer(serializers.ModelSerializer):
    yea_votes_count = serializers.SerializerMethodField()
    nay_votes_count = serializers.SerializerMethodField()
    present_votes_count = serializers.SerializerMethodField()
    proxy_votes_count = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    advisements = serializers.SerializerMethodField()

    class Meta:
        model = billModels.Bill
        fields = "__all__"
        extra_fields = ['url', 'advisements']

    def get_yea_votes_count(self, obj):
        return obj.count_yea_votes()

    def get_nay_votes_count(self, obj):
        return obj.count_nay_votes()

    def get_present_votes_count(self, obj):
        return obj.count_present_votes()

    def get_proxy_votes_count(self, obj):
        return obj.count_proxy_votes()

    def get_district_yea_votes_count(self, obj, district_code):
        return obj.count_district_yea_votes(district_code)

    def get_district_nay_votes_count(self, obj, district_code):
        return obj.count_district_nay_votes(district_code)

    def get_district_present_votes_count(self, obj, district_code):
        return obj.count_district_present_votes(district_code)

    def get_district_proxy_votes_count(self, obj, district_code):
        return obj.count_district_proxy_votes(district_code)

    def get_url(self, obj):
        request = self.context.get('request')
        return reverse('bill-detail', args=[obj.pk], request=request)
    
    def get_advisements(self, obj):
        """Get advisements from user's delegates for this bill"""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return {}
        
        user = request.user
        advisements = {}
        
        try:
            # Get First Delegate advisement
            from vote.models import GroupMember
            group_member = GroupMember.objects.filter(user=user).first()
            if group_member:
                f_del = GroupMember.objects.filter(
                    group=group_member.group,
                    is_delegate=True
                ).first()
                if f_del:
                    fd_advisement = billModels.BillAdvisement.objects.filter(
                        bill=obj, user=f_del.user, type='FD'
                    ).first()
                    if fd_advisement:
                        advisements['first_delegate'] = {
                            'advisement': fd_advisement.advisement,
                            'advisor': fd_advisement.user.username
                        }
            
            # Get Second Delegate advisement
            from api.models import SecDelMembers
            sec_del_member = SecDelMembers.objects.filter(user=user).first()
            if sec_del_member:
                sec_del = SecDelMembers.objects.filter(
                    sec_del=sec_del_member.sec_del,
                    is_delegate=True
                ).first()
                if sec_del:
                    sd_advisement = billModels.BillAdvisement.objects.filter(
                        bill=obj, user=sec_del.user, type='SD'
                    ).first()
                    if sd_advisement:
                        advisements['second_delegate'] = {
                            'advisement': sd_advisement.advisement,
                            'advisor': sd_advisement.user.username
                        }
            
            # Get MoDa advisement
            from moda.models import ModaMembers
            moda_member = ModaMembers.objects.filter(user=user).first()
            if moda_member:
                moda_del = ModaMembers.objects.filter(
                    moda=moda_member.moda,
                    is_delegate=True
                ).first()
                if moda_del:
                    md_advisement = billModels.BillAdvisement.objects.filter(
                        bill=obj, user=moda_del.user, type='MD'
                    ).first()
                    if md_advisement:
                        advisements['moda'] = {
                            'advisement': md_advisement.advisement,
                            'advisor': md_advisement.user.username
                        }
            
            # Get HoLC advisement
            from holc.models import HolcMembers
            holc_member = HolcMembers.objects.filter(user=user).first()
            if holc_member:
                holc_del = HolcMembers.objects.filter(
                    holc=holc_member.holc,
                    is_delegate=True
                ).first()
                if holc_del:
                    hl_advisement = billModels.BillAdvisement.objects.filter(
                        bill=obj, user=holc_del.user, type='HL'
                    ).first()
                    if hl_advisement:
                        advisements['holc'] = {
                            'advisement': hl_advisement.advisement,
                            'advisor': hl_advisement.user.username
                        }
            
            # Get House Rep advisement
            from rep.models import DistrictCouncilMembers
            rep_member = DistrictCouncilMembers.objects.filter(user=user).first()
            if rep_member:
                rep_del = DistrictCouncilMembers.objects.filter(
                    district_council=rep_member.district_council,
                    is_delegate=True
                ).first()
                if rep_del:
                    hr_advisement = billModels.BillAdvisement.objects.filter(
                        bill=obj, user=rep_del.user, type='HR'
                    ).first()
                    if hr_advisement:
                        advisements['house_rep'] = {
                            'advisement': hr_advisement.advisement,
                            'advisor': hr_advisement.user.username
                        }
                        
        except Exception as e:
            # If anything fails, return empty advisements
            pass
            
        return advisements



# create custom serializer of bill and voter for BillVoteSerializer
class CustomBillSerializer(serializers.ModelSerializer):
    class Meta:
        model = billModels.Bill
        fields = ['id','number', 'bill_type']
class CustomVoterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username']

class BillVoteSerializer(serializers.ModelSerializer):
    bill = CustomBillSerializer()
    voter = CustomVoterSerializer()
    class Meta:
        model = billModels.BillVote
        fields = ['id',"bill","voter","voted_by_fDel","your_vote","vote_date","last_update"]


class BillUserNotesSerializer(serializers.ModelSerializer):
    bill = CustomBillSerializer(read_only=True)
    user = CustomVoterSerializer(read_only=True)
    bill_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = billModels.BillUserNotes
        fields = ['id', 'created_at', 'updated_at', 'user', 'bill', 'note', 'bill_id']
        read_only_fields = ['created_at', 'updated_at', 'user']

    def create(self, validated_data):
        bill_id = validated_data.pop('bill_id')
        validated_data['bill_id'] = bill_id
        return super().create(validated_data)


class BillFirstDelNotesSerializer(serializers.ModelSerializer):
    bill = CustomBillSerializer(read_only=True)
    user = CustomVoterSerializer(read_only=True)
    bill_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = billModels.BillFirstDelNotes
        fields = ['id', 'created_at', 'updated_at', 'user', 'bill', 'note', 'bill_id']
        read_only_fields = ['created_at', 'updated_at', 'user']

    def create(self, validated_data):
        bill_id = validated_data.pop('bill_id')
        validated_data['bill_id'] = bill_id
        return super().create(validated_data)

    def validate(self, data):
        """Validate that the user is a first delegate"""
        from vote.models import GroupMember
        user = self.context['request'].user
        
        # Check if the user is actually a first delegate by looking at GroupMember records
        is_first_delegate = GroupMember.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_first_delegate:
            raise serializers.ValidationError("Only first delegates can create first delegate notes")
        return data

class BillSecondDelNotesSerializer(serializers.ModelSerializer):
    bill = CustomBillSerializer(read_only=True)
    user = CustomVoterSerializer(read_only=True)
    bill_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = billModels.BillSecondDelNotes
        fields = ['id', 'created_at', 'updated_at', 'user', 'bill', 'note', 'bill_id']
        read_only_fields = ['created_at', 'updated_at', 'user']

    def create(self, validated_data):
        bill_id = validated_data.pop('bill_id')
        validated_data['bill_id'] = bill_id
        return super().create(validated_data)

    def validate(self, data):
        """Validate that the user is a second delegate"""
        from api.models import SecDelMembers
        user = self.context['request'].user
        
        # Check if the user is actually a second delegate by looking at SecDelMembers records
        is_second_delegate = SecDelMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_second_delegate:
            raise serializers.ValidationError("Only second delegates can create second delegate notes")
        return data

class BillModaNotesSerializer(serializers.ModelSerializer):
    bill = CustomBillSerializer(read_only=True)
    user = CustomVoterSerializer(read_only=True)
    bill_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = billModels.BillModaNotes
        fields = ['id', 'created_at', 'updated_at', 'user', 'bill', 'note', 'bill_id']
        read_only_fields = ['created_at', 'updated_at', 'user']

    def create(self, validated_data):
        bill_id = validated_data.pop('bill_id')
        validated_data['bill_id'] = bill_id
        return super().create(validated_data)

    def validate(self, data):
        """Validate that the user is a MoDa"""
        from moda.models import ModaMembers
        user = self.context['request'].user
        
        # Check if the user is actually a MoDa by looking at ModaMembers records
        is_moda = ModaMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_moda:
            raise serializers.ValidationError("Only MoDa can create MoDa notes")
        return data

class BillHolcNotesSerializer(serializers.ModelSerializer):
    bill = CustomBillSerializer(read_only=True)
    user = CustomVoterSerializer(read_only=True)
    bill_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = billModels.BillHolcNotes
        fields = ['id', 'created_at', 'updated_at', 'user', 'bill', 'note', 'bill_id']
        read_only_fields = ['created_at', 'updated_at', 'user']

    def create(self, validated_data):
        bill_id = validated_data.pop('bill_id')
        validated_data['bill_id'] = bill_id
        return super().create(validated_data)

    def validate(self, data):
        """Validate that the user is a Holc"""
        from holc.models import HolcMembers
        user = self.context['request'].user
        
        # Check if the user is actually a MoDa by looking at ModaMembers records
        is_holc = HolcMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_holc:
            raise serializers.ValidationError("Only Holc can create Holc notes")
        return data
    

class BillHouseRepNotesSerializer(serializers.ModelSerializer):
    bill = CustomBillSerializer(read_only=True)
    user = CustomVoterSerializer(read_only=True)
    bill_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = billModels.BillHouseRepNotes
        fields = ['id', 'created_at', 'updated_at', 'user', 'bill', 'note', 'bill_id']
        read_only_fields = ['created_at', 'updated_at', 'user']

    def create(self, validated_data):
        bill_id = validated_data.pop('bill_id')
        validated_data['bill_id'] = bill_id
        return super().create(validated_data)

    def validate(self, data):
        """Validate that the user is a Holc"""
        from rep.models import DistrictCouncilMembers
        user = self.context['request'].user
        
        # Check if the user is actually a MoDa by looking at ModaMembers records
        is_house_rep = DistrictCouncilMembers.objects.filter(
            user=user,
            is_delegate=True
        ).exists()
        
        if not is_house_rep:
            raise serializers.ValidationError("Only House Rep can create House Rep notes")
        return data

class BillAdvisementSerializer(serializers.ModelSerializer):
    bill = CustomBillSerializer(read_only=True)
    user = CustomVoterSerializer(read_only=True)
    bill_id = serializers.IntegerField(write_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = billModels.BillAdvisement
        fields = ['id', 'created_at', 'last_update', 'user', 'bill', 'type', 'type_display', 'advisement', 'bill_id']
        read_only_fields = ['created_at', 'last_update', 'user']

    def create(self, validated_data):
        bill_id = validated_data.pop('bill_id')
        validated_data['bill_id'] = bill_id
        return super().create(validated_data)

    def validate(self, data):
        """Validate that the user has the correct delegate type"""
        user = self.context['request'].user
        delegate_type = data.get('type')
        
        # Check if the user has the correct delegate status
        if delegate_type == 'FD':
            from vote.models import GroupMember
            is_delegate = GroupMember.objects.filter(
                user=user,
                is_delegate=True
            ).exists()
            if not is_delegate:
                raise serializers.ValidationError("Only First Delegates can create FD advisements")
                
        elif delegate_type == 'SD':
            from api.models import SecDelMembers
            is_delegate = SecDelMembers.objects.filter(
                user=user,
                is_delegate=True
            ).exists()
            if not is_delegate:
                raise serializers.ValidationError("Only Second Delegates can create SD advisements")
                
        elif delegate_type == 'MD':
            from moda.models import ModaMembers
            is_delegate = ModaMembers.objects.filter(
                user=user,
                is_delegate=True
            ).exists()
            if not is_delegate:
                raise serializers.ValidationError("Only MoDa can create MD advisements")
                
        elif delegate_type == 'HL':
            from holc.models import HolcMembers
            is_delegate = HolcMembers.objects.filter(
                user=user,
                is_delegate=True
            ).exists()
            if not is_delegate:
                raise serializers.ValidationError("Only HoLC can create HL advisements")
                
        elif delegate_type == 'HR':
            from rep.models import DistrictCouncilMembers
            is_delegate = DistrictCouncilMembers.objects.filter(
                user=user,
                is_delegate=True
            ).exists()
            if not is_delegate:
                raise serializers.ValidationError("Only House Rep can create HR advisements")
        
        return data
