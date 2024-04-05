from rest_framework import serializers
from vote.models import Districts
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode
from vote.token import account_activation_token
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.validators import UniqueValidator
from django.contrib.auth.password_validation import validate_password
from vote import models as voteModels
from bills import models as billModels
import os
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from api import models as apiModels


class DistrictsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Districts
        fields = ['name', 'code']


def entry_code_generator():
    """
    this is the entry code generator.
    It uses random and checks for the database.
    return the code if it's not taken
    """
    import random
    code = str(random.choice('abcdefghijklmnpqrstuvwxyz'))
    code += str(random.randint(1, 9))
    code += str(random.choice('abcdefghijklmnpqrstuvwxyz'))
    code += str(random.randint(1, 9))
    code += str(random.choice('abcdefghijklmnpqrstuvwxyz'))
    code = code.upper()
    is_exist = User.objects.filter(username=code).exists()

    if is_exist:
        entry_code_generator()
    return code


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
    address = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'password2', 'email',
                  'district', 'legalName', 'is_reg', 'is_reg1', 'address')
        # extra_kwargs = {
        #     'first_name': {'required': True},
        #     'last_name': {'required': True}
        # }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."})

        return attrs

    def create(self, validated_data):
        user = User.objects.create(
            username=entry_code_generator(),
            email=validated_data['email'],
            is_active=True,  # change this to True siva
            # first_name=validated_data['first_name'],
            # last_name=validated_data['last_name']
        )

        user.set_password(validated_data['password'])
        user.save()
        # set the user profile instance
        user.users.legalName = validated_data['legalName'].upper()

        user.users.address = validated_data['address']

        # add user district
        from vote.models import Districts
        dist = Districts.objects.filter(
            code=validated_data['district'].upper()).first()
        if not dist:
            raise serializers.ValidationError(
                {"district": "district didn't match."})

        user.users.district = dist

        # set if user should be notified within 30 days
        if validated_data['is_reg1']:
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
        send_mail(mail_subject, message,
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


class PodSerializer(serializers.ModelSerializer):
    district = DistrictsSerializer()
    # is_active is a property defined on the model
    is_active = serializers.ReadOnlyField()

    class Meta:
        model = voteModels.Pod
        fields = "__all__"


class PodMember_VoteInSer(serializers.ModelSerializer):
    class Meta:
        model = voteModels.PodMember_vote_in
        fields = '__all__'


class PodMember_put_farwardSer(serializers.ModelSerializer):
    class Meta:
        model = voteModels.PodMember_put_farward
        fields = '__all__'


class PodMember_VoteOutSer(serializers.ModelSerializer):
    class Meta:
        model = voteModels.PodMember_vote_out
        fields = '__all__'


class PODMemberSer(serializers.ModelSerializer):
    user = UserSerializer()
    pod = PodSerializer()
    voteIns = serializers.StringRelatedField(many=True)
    voteOuts = serializers.StringRelatedField(many=True)
    putFarward = serializers.StringRelatedField(many=True)

    class Meta:
        model = voteModels.PodMember
        fields = ["is_delegate", "member_number", "id", 'user',
                  'pod', "is_member", 'voteIns', 'voteOuts', 'putFarward']


# This serializer is being used in Circle consumer file for pod members
class Userial(serializers.ModelSerializer):
    class Meta:
        model = voteModels.Users
        fields = ["id", "legalName", "is_reg",
                  "verificationScore", "address", "userType", "VVAT_Number"]

# this serializer is being used in Circle consumer file for pod members


class User_Serializer(serializers.ModelSerializer):
    users = Userial()

    class Meta:
        model = User
        fields = ["id", "username", "email", "date_joined", "users"]


# this serializer is being used in Circle consumer file for pod members
class PodMemberSerializer(serializers.ModelSerializer):
    user = User_Serializer()
    pod = PodSerializer()

    class Meta:
        model = voteModels.PodMember
        fields = ['id', 'is_member', 'is_delegate',
                  'date_joined', 'date_updated', 'pod', 'user', 'count_vote_in',
                  'count_vote_out', 'count_put_farward']


class VoterPageSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = voteModels.Users
        fields = "__all__"
        depth = 1


class PodBackNForthSerializer(serializers.ModelSerializer):
    sender = UserSerializer()

    class Meta:
        model = voteModels.PodBackNForth
        fields = ["id", "sender", "message", "pod", 'date']


class CircleStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = voteModels.CircleStatus
        fields = "__all__"


class TestingSerializer(serializers.ModelSerializer):
    class Meta:
        model = apiModels.TestingModel
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
