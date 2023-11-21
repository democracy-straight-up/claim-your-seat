from rest_framework import serializers
from bills import models as billModels
from django.contrib.auth.models import User
from vote.models import Pod

class BillSerializer(serializers.ModelSerializer):
    yea_votes_count = serializers.SerializerMethodField()
    nay_votes_count = serializers.SerializerMethodField()
    present_votes_count = serializers.SerializerMethodField()
    proxy_votes_count = serializers.SerializerMethodField()
    class Meta:
        model = billModels.Bill
        fields = "__all__" 
    
    def get_yea_votes_count(self, obj):
        # Use the count_yea_votes method from your Bill model
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



# create custom serializer of bill and voter for BillVoteSerializer
class CustomBillSerializer(serializers.ModelSerializer):
    class Meta:
        model = billModels.Bill
        fields = ['id','number', 'bill_type']
class CustomVoterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username']

class CustomPodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pod
        fields = ['id','code']

class BillVoteSerializer(serializers.ModelSerializer):
    bill = CustomBillSerializer()
    voter = CustomVoterSerializer()
    class Meta:
        model = billModels.BillVote
        fields = ['id',"bill","voter","voted_by_fDel","your_vote","vote_date","last_update"]


class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)

        # Instantiate the superclass normally
        super(DynamicFieldsModelSerializer, self).__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields.keys())
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class AdviceSerializer(DynamicFieldsModelSerializer):
    bill = CustomBillSerializer()
    voter = CustomVoterSerializer()
    pod = CustomPodSerializer()
    username = serializers.CharField(source='voter.username')
    class Meta:
        model = billModels.Advice
        fields = ['id',"bill","voter","pod","advice","username"]

