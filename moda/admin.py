from django.contrib import admin
from moda import models as modaModels


class Moda_Admin(admin.ModelAdmin):
    list_display =['code','invitation_key', 'is_active','member_count', 'district','created_at']
    list_display_links =['code','invitation_key',  'is_active', 'district','created_at']
    search_fields =['code','invitation_key','district', 'is_active','created_at']
admin.site.register(modaModels.ModaModel, Moda_Admin)

class ModaMembers_Admin(admin.ModelAdmin):
    list_display =['user','moda','is_delegate','is_member','joined_at']
    list_display_links =['user','moda','is_delegate','is_member','joined_at']
    search_fields =['user__username','moda__code','is_delegate','is_member','joined_at']
admin.site.register(modaModels.ModaMembers, ModaMembers_Admin)