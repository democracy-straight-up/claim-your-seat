from django.contrib import admin
from api import models as apiModels


class SecDel_Admin(admin.ModelAdmin):
    list_display =['code','invitation_key', 'is_active', 'district','created_at']
    list_display_links =['code','invitation_key',  'is_active', 'district','created_at']
    search_fields =['code','invitation_key','district', 'is_active','created_at']
admin.site.register(apiModels.SecDelModel, SecDel_Admin)


class SecDelMembers_Admin(admin.ModelAdmin):
    list_display =['user','sec_del', 'is_member', 'is_delegate','joined_at']
    list_display_links =['user','sec_del', 'is_member', 'is_delegate','joined_at']
    search_fields =['user','sec_del', 'is_member', 'is_delegate','joined_at']
admin.site.register(apiModels.SecDelMembers, SecDelMembers_Admin)

class SecDelMembersVoteOut_Admin(admin.ModelAdmin):
    list_display =[ 'voted_at','candidate','sec_del', 'voter']
    list_display_links =['voted_at','candidate','sec_del', 'voter']
    search_fields =['voted_at','candidate','sec_del', 'voter']
admin.site.register(apiModels.VoteOutSecDelMember, SecDelMembersVoteOut_Admin)

class SecDelMembersVoteIn_Admin(admin.ModelAdmin):
    list_display =[ 'voted_at','candidate','sec_del', 'voter']
    list_display_links =['voted_at','candidate','sec_del', 'voter']
    search_fields =['voted_at','candidate','sec_del', 'voter']
admin.site.register(apiModels.VoteInSecDelMember, SecDelMembersVoteIn_Admin)

class SecDelMembersPutFarward_Admin(admin.ModelAdmin):
    list_display =[ 'voted_at','candidate', 'sec_del', 'voter']
    list_display_links =['voted_at','candidate', 'sec_del', 'voter']
    search_fields =['voted_at','candidate', 'sec_del', 'voter']
admin.site.register(apiModels.PutFarwardSecDelMember, SecDelMembersPutFarward_Admin)

class DummyVoters_Admin(admin.ModelAdmin):
    list_display =['voters','circle', 'district', 'f_link','created_at', 'text']
    list_display_links =['voters','circle', 'district', 'f_link','created_at', 'text']
    search_fields =[ 'district', 'created_at', 'text']

admin.site.register(apiModels.DummyVoters, DummyVoters_Admin)

class StatusItems_Admin(admin.ModelAdmin):
    list_display =['is_active','is_for_candidate', 'sort','is_candidate_waiting', 'is_for_member', 'is_for_delegate', 'message','item_list', 'is_for_circle', 'is_for_sec_del', 'is_for_moda']
    
    list_display_links =['is_active','is_for_candidate', 'is_for_member', 'is_for_delegate', 'is_for_circle', 'is_for_sec_del', 'is_for_moda',
                    'message','item_list', ]
    search_fields =['message','item_list', 'is_for_member', 'is_for_delegate','is_for_candidate' ,'is_for_circle', 'is_for_sec_del', 'is_for_moda']

admin.site.register(apiModels.StatusItems, StatusItems_Admin)