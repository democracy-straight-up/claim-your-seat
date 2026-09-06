from rest_framework import serializers
from vote.models import Districts
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from vote.token import account_activation_token
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
import vote.models as voteModels
import os
from api.utils import entry_code_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

class DistrictsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Districts
        fields = ['name', 'code']


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True, validators=[
                                   UniqueValidator(queryset=User.objects.all())])
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    district = serializers.CharField(write_only=True)
    legalName = serializers.CharField(write_only=True)
    is_reg = serializers.BooleanField(required=False)
    is_reg1 = serializers.BooleanField(required=False)
    eligibility_attested = serializers.BooleanField(write_only=True, required=True)
    address = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email',
                  'district', 'legalName', 'is_reg', 'is_reg1', 'address', 'eligibility_attested')
        # extra_kwargs = {
        #     'first_name': {'required': True},
        #     'last_name': {'required': True}
        # }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."})
        if not attrs.get('eligibility_attested'):
            raise serializers.ValidationError({
                "eligibility_attested": "You must certify that you are legally eligible to vote in this district."
            })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        dist = Districts.objects.filter(
            code=validated_data['district'].upper()).first()

        if not dist:
            raise serializers.ValidationError(
                {"district": "district didn't match."})
        user = User.objects.create(
            username=entry_code_generator(),
            email=validated_data['email'],
            is_active=False,
            # first_name=validated_data['first_name'],
            # last_name=validated_data['last_name']
        )

        user.set_password(validated_data['password'])
        user.save()
        # set the user profile instance
        user.users.legalName = validated_data['legalName'].upper()
        user.users.address = validated_data['address']

        # add user district

        user.users.district = dist
        if validated_data.get('eligibility_attested', False):
            user.users.eligibility_attested = True
            user.users.eligibility_attested_at = timezone.now()
            user.users.eligibility_attestation_version = 'legal-voter-v1'
        # set if user should be notified within 30 days
        if validated_data.get('is_reg1', False):
            user.users.is_reg = True

        def get_vvat_number():
            import random
            import string
            district = validated_data['district'].upper()
            letter = random.choice(string.ascii_uppercase.replace('I', '').replace('O', ''))
            numbers = ''.join(random.choices(string.digits, k=6))
            vvat_number = f"{district[:4]}{letter}{numbers}"
            return vvat_number

        # add VVAT_Number to the users
        user.users.VVAT_Number = get_vvat_number()

        user.save()
        # send email and get url and encode
        mail_subject = 'Activate your account.'
        message = render_to_string('api/accountActiveEmail.html', {
            'user': user,
            'domain': os.environ.get('APP_DOMAIN'),
            'protocol': 'https' if self.context['request'].is_secure() else 'http',
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': account_activation_token.make_token(user),
        })
        ad = send_mail(mail_subject, message,
                  settings.EMAIL_HOST_USER, [user.email])

        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, value):
        try:
            # check if the user with the given email exists
            email = value.get('email')
            User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "User with given email does not exist")
        return value


class PasswordResetSerializer(serializers.Serializer):
    # uidb64 is the user id encoded in base64
    uidb64 = serializers.CharField(required=True)
    # TODO: add a new generator for the token
    # token is the token generated by the account_activation_token
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password])
    new_password2 = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError(
                {"new_password2": "Password fields didn't match."})

        try:
            # decode the uidb64 to get the user id
            uid = force_str(urlsafe_base64_decode(attrs['uidb64']))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"uidb64": "User is not exist."})

        if not account_activation_token.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token": "Token is not valid."})

        attrs['user'] = user
        return attrs


class Userializer(serializers.ModelSerializer):
    district = DistrictsSerializer()

    class Meta:
        model = voteModels.Users
        fields = ["legalName", "district", "is_reg",
                  "verificationScore", "address", "userType", "VVAT_Number"]


class UserSerializer(serializers.HyperlinkedModelSerializer):
    users = Userializer()

    class Meta:
        model = User
        fields = ["id", "username", "email", "is_staff",
                  "is_active", "users", "date_joined"]
        depth = 1


class CircleSerializer(serializers.ModelSerializer):
    district = DistrictsSerializer()
    # is_active is a property defined on the model
    # is_active = serializers.ReadOnlyField()
    member_count = serializers.ReadOnlyField()
    class Meta:
        model = voteModels.Group
        fields = "__all__"


class CircleMember_VoteInSer(serializers.ModelSerializer):
    class Meta:
        model = voteModels.CircleMember_vote_in
        fields = '__all__'


class CircleMember_put_forwardSer(serializers.ModelSerializer):
    class Meta:
        model = voteModels.CircleMember_put_forward
        fields = '__all__'


class CircleMember_VoteOutSer(serializers.ModelSerializer):
    class Meta:
        model = voteModels.CircleMember_vote_out
        fields = '__all__'



class CIRCLEMemberSer(serializers.ModelSerializer):
    user = UserSerializer()
    circle = CircleSerializer()
    voteIns = serializers.StringRelatedField(many=True)
    voteOuts = serializers.StringRelatedField(many=True)
    putForward = serializers.StringRelatedField(many=True)
    class Meta:
        model = voteModels.GroupMember
        fields = ["is_delegate", "member_number", "id", 'user',
                  'circle', "is_member", 'voteIns', 'voteOuts', 'putForward']


# This serializer is being used in Circle consumer file for circle members
class Userial(serializers.ModelSerializer):
    class Meta:
        model = voteModels.Users
        fields = ["id", "legalName", "is_reg",
                  "verificationScore", "address", "userType", "VVAT_Number"]

# this serializer is being used in Circle consumer file for circle members


class User_Serializer(serializers.ModelSerializer):
    users = Userial()

    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined", "users"]


# this serializer is being used in Circle consumer file for circle members
class CircleMemberSerializer(serializers.ModelSerializer):
    user = User_Serializer()
    group = CircleSerializer()
    voteIns = serializers.StringRelatedField(many=True)
    voteOuts = serializers.StringRelatedField(many=True)
    putForward = serializers.StringRelatedField(many=True)
    count_vote_in = serializers.StringRelatedField()
    count_vote_out = serializers.StringRelatedField()
    count_put_forward = serializers.StringRelatedField()

    class Meta:
        model = voteModels.GroupMember
        fields = ['id', 'is_member', 'is_delegate', 'voteIns', 'voteOuts', 'putForward',
                  'date_joined', 'date_updated', 'group', 'user', 'count_vote_in',
                  'count_vote_out', 'count_put_forward']


class VoterPageSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = voteModels.Users
        fields = "__all__"
        depth = 1


class CircleBackNForthSerializer(serializers.ModelSerializer):
    sender = UserSerializer()

    class Meta:
        model = voteModels.CircleBackNForth
        fields = ["id", "sender", "message", "circle", 'date']


class CircleStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = voteModels.CircleStatus
        fields = "__all__"

class UsernameRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate(self, value):
        try:
            email = value.get('email')
            User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "User with given email does not exist")
        return value

# Contact Serializers for each member type
class GroupMemberContactInfoSerializer(serializers.ModelSerializer):
    member = CircleMemberSerializer(read_only=True)
    class Meta:
        model = voteModels.ContactInfo
        fields = ['id', 'member', 'group', 'legal_name', 'contact_rules', 'address',
                  'contact', 'phone', 'email', 'created_at']
        read_only_fields = ['created_at',]

