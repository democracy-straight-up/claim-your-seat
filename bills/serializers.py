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

    class Meta:
        model = billModels.Bill
        fields = "__all__"
        extra_fields = ['url']

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