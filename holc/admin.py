
from django.contrib import admin
from holc import models as holcModels


class Holc_Admin(admin.ModelAdmin):
    list_display =['code','invitation_key', 'is_active','member_count', 'district','created_at']
    list_display_links =['code','invitation_key',  'is_active', 'district','created_at']
    search_fields =['code','invitation_key','district', 'is_active','created_at']
admin.site.register(holcModels.HolcModel, Holc_Admin)

class HolcMembers_Admin(admin.ModelAdmin):
    list_display =['user','holc','is_delegate','is_member','joined_at']
    list_display_links =['user','holc','is_delegate','is_member','joined_at']
    search_fields =['user__username','holc__code','is_delegate','is_member','joined_at']
admin.site.register(holcModels.HolcMembers, HolcMembers_Admin)

class HolcMembersVoteOut_Admin(admin.ModelAdmin):
    list_display =[ 'voted_at','candidate','holc', 'voter']
    list_display_links =['voted_at','candidate','holc', 'voter']
    search_fields =['voted_at','candidate','holc', 'voter']
admin.site.register(holcModels.VoteOutHolcMember, HolcMembersVoteOut_Admin)

class HolcMembersVoteIn_Admin(admin.ModelAdmin):
    list_display =[ 'voted_at','candidate','holc', 'voter']
    list_display_links =['voted_at','candidate','holc', 'voter']
    search_fields =['voted_at','candidate','holc', 'voter']
admin.site.register(holcModels.VoteInHolcMember, HolcMembersVoteIn_Admin)

class HolcMembersPutFarward_Admin(admin.ModelAdmin):
    list_display =[ 'voted_at','candidate', 'holc', 'voter']
    list_display_links =['voted_at','candidate', 'holc', 'voter']
    search_fields =['voted_at','candidate', 'holc', 'voter']
admin.site.register(holcModels.PutFarwardHolcMember, HolcMembersPutFarward_Admin)
