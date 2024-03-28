from django.contrib import admin
from vote import models

class DistrictAdmin(admin.ModelAdmin):
    list_display = ['name','code']
    list_display_links = ["name", "code"]
admin.site.register(models.Districts, DistrictAdmin)

class UsersAdmin(admin.ModelAdmin):
    list_display = ['user','legalName', 'district', 'is_reg', 'verificationScore', 'userType', 'VVAT_Number']
    list_display_links = ["user", "legalName", 'district']
    list_filter = [ 'is_reg', 'verificationScore', 'userType']
admin.site.register(models.Users, UsersAdmin)

class PodAdmin(admin.ModelAdmin):
    list_display = ['code', 'invitation_code', 'district']
    list_display_links = ["code", "invitation_code", "district"]
    list_filter = ['district']
admin.site.register(models.Pod, PodAdmin)

class PodMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'pod', 'is_member', 'is_delegate', 'member_number']
    list_display_links = ["user", "pod", "is_member", "member_number"]
    list_filter = ['is_member', 'is_delegate']
admin.site.register(models.PodMember, PodMemberAdmin)

class PodMember_vote_inAdmin(admin.ModelAdmin):
    list_display = ['condidate', 'voter']
    list_display_links = ["condidate", "voter"]
admin.site.register(models.PodMember_vote_in, PodMember_vote_inAdmin)

class PodMember_vote_outAdmin(admin.ModelAdmin):
    list_display = ['condidate', 'voter']
    list_display_links = ["condidate", "voter"]
admin.site.register(models.PodMember_vote_out, PodMember_vote_outAdmin)

class PodMember_put_farwardAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'voter']
    list_display_links = ["recipient", "voter"]
admin.site.register(models.PodMember_put_farward, PodMember_put_farwardAdmin)

class PodBackNForthAdmin(admin.ModelAdmin):
    list_display = ['pod', 'sender', 'date', 'message']
    list_display_links = ["pod", "sender", "date"]
admin.site.register(models.PodBackNForth,PodBackNForthAdmin)

class CircleStatusAdmin(admin.ModelAdmin):
    list_display = ['message', 'is_delegate', 'is_candidate', 'is_member','is_activeCircle']
    list_display_links = ["message"]
    list_filter = ['is_member', 'is_delegate','is_candidate','is_activeCircle']
    search_fields = ['message']

admin.site.register(models.CircleStatus,CircleStatusAdmin)


class PodMemberContact_Admin(admin.ModelAdmin):
    list_display = ['member', 'pod', 'email', 'phone']
    list_display_links = ['member', 'pod', 'email', 'phone']
    list_filter = ['member', 'pod', 'email', 'phone']
    search_fields = ['member', 'pod', 'email', 'phone']


admin.site.register(models.PodMemberContact, PodMemberContact_Admin)
