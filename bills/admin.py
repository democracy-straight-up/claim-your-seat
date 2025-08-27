from django.contrib import admin

# Register your models here.
import bills.models as models

class BillAdmin(admin.ModelAdmin):
    list_display = ['number','title','bill_type','congress','latest_action_date','schedule_date','created_at', 'updated_at']
    list_display_links = ["number", "title"]
    list_filter = ['bill_type', 'congress', 'schedule_date', 'created_at', 'updated_at']
    search_fields = ['number', 'title', 'latest_action_text']

admin.site.register(models.Bill, BillAdmin)

class BillVoteAdmin(admin.ModelAdmin):
    list_display = ['bill', 'voter', 'your_vote','vote_date', 'last_update']
    list_filter = ['vote_date', 'last_update', 'your_vote']
    list_display_links = ["bill",'voter', 'your_vote']
admin.site.register(models.BillVote, BillVoteAdmin)

class BillUserNotesAdmin(admin.ModelAdmin):
    list_display = ['bill', 'user', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    list_display_links = ['bill', 'user']
    search_fields = ['bill__number', 'user__username', 'note']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(models.BillUserNotes, BillUserNotesAdmin)

class BillFirstDelNotesAdmin(admin.ModelAdmin):
    list_display = ['bill', 'user', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    list_display_links = ['bill', 'user']
    search_fields = ['bill__number', 'user__username', 'note']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(models.BillFirstDelNotes, BillFirstDelNotesAdmin)

class BillSecondDelNotesAdmin(admin.ModelAdmin):
    list_display = ['bill', 'user', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    list_display_links = ['bill', 'user']
    search_fields = ['bill__number', 'user__username', 'note']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(models.BillSecondDelNotes, BillSecondDelNotesAdmin)

class BillModaNotesAdmin(admin.ModelAdmin):
    list_display = ['bill', 'user', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    list_display_links = ['bill', 'user']
    search_fields = ['bill__number', 'user__username', 'note']
    readonly_fields = ['created_at', 'updated_at']

admin.site.register(models.BillModaNotes, BillModaNotesAdmin)
