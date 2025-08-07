
from django.contrib import admin
from rep import models as repModels


class RepAdmin(admin.ModelAdmin):
    list_display =['code','invitation_key', 'status','member_count', 'district','created_at']
    list_display_links =['code','invitation_key',  'status', 'district','created_at']
    search_fields =['code','invitation_key','district', 'status','created_at']
admin.site.register(repModels.DistrictCouncil, RepAdmin)

class RepMembers_Admin(admin.ModelAdmin):
    list_display =['user','district_council','is_delegate','is_member','joined_at']
    list_display_links =['user','district_council','is_delegate','is_member','joined_at']
    search_fields =['user__username','district_council__code','is_delegate','is_member','joined_at']
admin.site.register(repModels.DistrictCouncilMembers, RepMembers_Admin)

class RepMembersVoteOut_Admin(admin.ModelAdmin):
    list_display =[ 'voted_at','candidate','district_council', 'voter']
    list_display_links =['voted_at','candidate','district_council', 'voter']
    search_fields =['voted_at','candidate','district_council', 'voter']
admin.site.register(repModels.VoteOutDistrictCouncilMember, RepMembersVoteOut_Admin)

class RepMembersVoteIn_Admin(admin.ModelAdmin):
    list_display =[ 'voted_at','candidate','district_council', 'voter']
    list_display_links =['voted_at','candidate','district_council', 'voter']
    search_fields =['voted_at','candidate','district_council', 'voter']
admin.site.register(repModels.VoteInDistrictCouncilMember, RepMembersVoteIn_Admin)

class RepMembersPutForward_Admin(admin.ModelAdmin):
    list_display =[ 'voted_at','candidate', 'district_council', 'voter']
    list_display_links =['voted_at','candidate', 'district_council', 'voter']
    search_fields =['voted_at','candidate', 'district_council', 'voter']
admin.site.register(repModels.PutForwardDistrictCouncilMember, RepMembersPutForward_Admin)
