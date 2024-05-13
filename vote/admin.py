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

class CircleAdmin(admin.ModelAdmin):
    list_display = ['code', 'invitation_code', 'district']
    list_display_links = ["code", "invitation_code", "district"]
    list_filter = ['district']
admin.site.register(models.Group, CircleAdmin)

class CircleMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'is_member', 'is_delegate', 'member_number']
    list_display_links = ["user", "group", "is_member", "member_number"]
    list_filter = ['is_member', 'is_delegate']
admin.site.register(models.GroupMember, CircleMemberAdmin)

class CircleMember_vote_inAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'voter']
    list_display_links = ["recipient", "voter"]
admin.site.register(models.CircleMember_vote_in, CircleMember_vote_inAdmin)

class CircleMember_vote_outAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'voter']
    list_display_links = ["candidate", "voter"]
admin.site.register(models.CircleMember_vote_out, CircleMember_vote_outAdmin)

class CircleMember_put_forwardAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'voter']
    list_display_links = ["recipient", "voter"]
admin.site.register(models.CircleMember_put_forward, CircleMember_put_forwardAdmin)

class CircleBackNForthAdmin(admin.ModelAdmin):
    list_display = ['circle', 'sender', 'date', 'message']
    list_display_links = ["circle", "sender", "date"]
admin.site.register(models.CircleBackNForth,CircleBackNForthAdmin)

class CircleStatusAdmin(admin.ModelAdmin):
    list_display = ['message', 'is_delegate', 'is_candidate', 'is_member','is_activeCircle']
    list_display_links = ["message"]
    list_filter = ['is_member', 'is_delegate','is_candidate','is_activeCircle']
    search_fields = ['message']

admin.site.register(models.CircleStatus,CircleStatusAdmin)


class CircleMemberContact_Admin(admin.ModelAdmin):
    list_display = ['member', 'group', 'email', 'phone']
    list_display_links = ['member', 'group', 'email', 'phone']
    list_filter = ['member', 'group', 'email', 'phone']
    search_fields = ['member', 'group', 'email', 'phone']


admin.site.register(models.GroupMemberContact, CircleMemberContact_Admin)
