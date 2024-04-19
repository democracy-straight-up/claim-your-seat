from django.contrib import admin

# Register your models here.
import bills.models as models

class BillAdmin(admin.ModelAdmin):
    list_display = ['number','title','schedule_date','created_at', 'updated_at']
    list_display_links = ["number", "title"]
    list_filter = ['schedule_date', 'created_at', 'updated_at']

admin.site.register(models.Bill, BillAdmin)

class BillVoteAdmin(admin.ModelAdmin):
    list_display = ['bill', 'voter', 'your_vote','vote_date', 'last_update']
    list_filter = ['vote_date', 'last_update', 'your_vote']
    list_display_links = ["bill",'voter', 'your_vote']
admin.site.register(models.BillVote, BillVoteAdmin)
