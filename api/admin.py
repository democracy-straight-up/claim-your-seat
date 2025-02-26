from django.contrib import admin
from api import models as apiModels


class SecDel_Admin(admin.ModelAdmin):
    list_display =['code','invitation_key', 'is_active', 'district','created_at']
    list_display_links =['code','invitation_key',  'is_active', 'district','created_at']
    search_fields =['code','invitation_key','district', 'is_active','created_at']
admin.site.register(apiModels.SecDelModel, SecDel_Admin)


class SecDelMembers_Admin(admin.ModelAdmin):
    list_display =['user','sec_del', 'vote_in_count','vote_out_count', 'is_member', 'is_delegate','joined_at']
    list_display_links =['user','sec_del', 'is_member', 'is_delegate','joined_at']
    search_fields =['user','sec_del', 'is_member', 'is_delegate','joined_at']
admin.site.register(apiModels.SecDelMembers, SecDelMembers_Admin)

class DummyVoters_Admin(admin.ModelAdmin):
    list_display =['voters','circle', 'district', 'f_link','created_at', 'text']
    list_display_links =['voters','circle', 'district', 'f_link','created_at', 'text']
    search_fields =[ 'district', 'created_at', 'text']

admin.site.register(apiModels.DummyVoters, DummyVoters_Admin)