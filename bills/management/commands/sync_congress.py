import requests
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from bills.models import Bill

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sync Congress.gov API data with local database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test',
            action='store_true',
            help='Test API connection only',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Number of bills to fetch per API request (batch size)',
        )
        parser.add_argument(
            '--max-batches',
            type=int,
            default=None,
            help='Maximum number of batches to process (for testing)',
        )

    def handle(self, *args, **options):
        if options['test']:
            self.test_api_connection()
        else:
            self.sync_congress_data(options['limit'], options.get('max_batches'))

    def test_api_connection(self):
        """Test Congress API connection"""
        self.stdout.write("🔍 Testing Congress API connection...")
        
        api_key = getattr(settings, 'CONGRESS_API_KEY', None)
        if not api_key:
            self.stdout.write(
                self.style.ERROR("❌ CONGRESS_API_KEY not set in environment variables")
            )
            return

        try:
            headers = {'x-api-key': api_key}
            params = {'offset': 0, 'limit': 5, 'format': 'json'}
            
            response = requests.get(
                'https://api.congress.gov/v3/bill',
                headers=headers,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            bills_count = len(data.get('bills', []))
            total_count = data.get('pagination', {}).get('count', 0)
            
            self.stdout.write(
                self.style.SUCCESS(f"✅ API connection successful!")
            )
            self.stdout.write(f"   Bills returned: {bills_count}")
            self.stdout.write(f"   Total available: {total_count}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ API connection failed: {str(e)}")
            )

    def sync_congress_data(self, limit=100, max_batches=None):
        """Sync Congress API data in batches"""
        self.stdout.write("🇺🇸 Starting Congress API sync...")
        
        api_key = getattr(settings, 'CONGRESS_API_KEY', None)
        if not api_key:
            self.stdout.write(
                self.style.ERROR("❌ CONGRESS_API_KEY not set in environment variables")
            )
            return

        new_bills = 0
        updated_bills = 0
        errors = 0
        total_processed = 0
        batch_count = 0
        
        try:
            # Process bills in batches
            offset = 0
            
            while True:
                batch_count += 1
                
                # Check if we've reached max batches limit (for testing)
                if max_batches and batch_count > max_batches:
                    self.stdout.write(f"⚠️ Reached maximum batch limit ({max_batches})")
                    break
                
                self.stdout.write(f"\n📥 Batch {batch_count}: Fetching bills starting at offset {offset}...")
                
                # Fetch one batch of bills
                bills_batch = self.fetch_bills_batch(api_key, limit, offset)
                
                if not bills_batch:
                    self.stdout.write("✅ No more bills to fetch")
                    break
                
                # Filter for HR bills from Congress 119 in this batch
                hr_bills_batch = [
                    bill for bill in bills_batch 
                    if bill.get('type') == 'HR' and bill.get('congress') == 119
                ]
                
                self.stdout.write(f"Found {len(hr_bills_batch)} HR bills from Congress 119 in this batch")
                
                # Process each bill in this batch
                batch_new, batch_updated, batch_errors = self.process_bills_batch(hr_bills_batch, api_key)
                
                new_bills += batch_new
                updated_bills += batch_updated
                errors += batch_errors
                total_processed += len(bills_batch)
                
                self.stdout.write(f"📊 Batch {batch_count} complete: +{batch_new} new, ~{batch_updated} updated, ❌{batch_errors} errors")
                self.stdout.write(f"📈 Total processed so far: {total_processed} bills")
                
                # Move to next batch
                offset += limit
                
                # Safety check to prevent infinite loops
                if offset > 50000:  # Reasonable upper limit
                    self.stdout.write("⚠️ Reached safety limit of 50,000 bills")
                    break
            
            # Final summary
            self.stdout.write("\n" + "="*60)
            self.stdout.write(self.style.SUCCESS("📊 SYNC COMPLETED"))
            self.stdout.write(f"🆕 New bills: {new_bills}")
            self.stdout.write(f"📝 Updated bills: {updated_bills}")
            self.stdout.write(f"❌ Errors: {errors}")
            self.stdout.write(f"📈 Total bills processed: {total_processed}")
            self.stdout.write(f"📦 Batches processed: {batch_count}")
            self.stdout.write(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Fatal error during sync: {str(e)}")
            )

    def fetch_bills_batch(self, api_key, limit, offset):
        """Fetch a single batch of bills from Congress API"""
        headers = {'x-api-key': api_key}
        params = {'offset': offset, 'limit': limit, 'format': 'json'}
        
        try:
            response = requests.get(
                'https://api.congress.gov/v3/bill',
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            bills = data.get('bills', [])
            
            # Show pagination info
            pagination = data.get('pagination', {})
            total_count = pagination.get('count', 0)
            self.stdout.write(f"  📄 Got {len(bills)} bills (total available: {total_count})")
            
            return bills
            
        except Exception as e:
            self.stdout.write(f"  ❌ Error fetching bills at offset {offset}: {str(e)}")
            return []

    def process_bills_batch(self, hr_bills_batch, api_key):
        """Process a batch of HR bills"""
        batch_new = 0
        batch_updated = 0
        batch_errors = 0
        
        with transaction.atomic():
            for i, bill_data in enumerate(hr_bills_batch):
                try:
                    bill_number = bill_data.get('number')
                    self.stdout.write(f"  🔄 Processing {i+1}/{len(hr_bills_batch)}: HR {bill_number}")
                    
                    # Get detailed bill info
                    detailed_data = self.fetch_bill_details(
                        bill_data.get('congress'),
                        bill_data.get('type'),
                        bill_number,
                        api_key
                    )
                    
                    # Merge data
                    merged_data = {**bill_data, **detailed_data}
                    
                    # Check if bill exists
                    existing_bill = Bill.objects.filter(
                        number=bill_number,
                        congress=bill_data.get('congress'),
                        bill_type=bill_data.get('type')
                    ).first()
                    
                    if existing_bill:
                        if self.update_bill(existing_bill, merged_data):
                            batch_updated += 1
                            self.stdout.write(f"    ✅ Updated HR {bill_number}")
                        else:
                            self.stdout.write(f"    ➡️ No changes for HR {bill_number}")
                    else:
                        self.create_bill(merged_data)
                        batch_new += 1
                        self.stdout.write(f"    🆕 Created HR {bill_number}")
                        
                except Exception as e:
                    batch_errors += 1
                    self.stdout.write(
                        self.style.ERROR(f"    ❌ Error processing HR {bill_data.get('number')}: {str(e)}")
                    )
        
        return batch_new, batch_updated, batch_errors

    def fetch_bill_details(self, congress, bill_type, bill_number, api_key):
        """Fetch detailed bill information"""
        details = {}
        base_url = f"https://api.congress.gov/v3/bill/{congress}/{bill_type.lower()}/{bill_number}"
        headers = {'x-api-key': api_key}
        
        try:
            # Get basic bill details
            response = requests.get(f"{base_url}?format=json", headers=headers, timeout=30)
            if response.status_code == 200:
                bill_data = response.json()
                details.update(bill_data.get('bill', {}))
            
            # Get committees (optional)
            try:
                committees_response = requests.get(f"{base_url}/committees?format=json", headers=headers, timeout=10)
                if committees_response.status_code == 200:
                    committees_data = committees_response.json()
                    details['committees_detail'] = committees_data.get('committees', [])
            except:
                pass  # Skip if committees endpoint fails
            
        except Exception as e:
            self.stdout.write(f"    Warning: Could not fetch details for {bill_number}: {str(e)}")
        
        return details

    def create_bill(self, bill_data):
        """Create a new bill record"""
        # Parse dates safely
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return None

        # Extract data
        latest_action = bill_data.get('latestAction', {})
        
        bill = Bill.objects.create(
            congress=bill_data.get('congress'),
            number=bill_data.get('number'),
            origin_chamber=bill_data.get('originChamber', ''),
            origin_chamber_code=bill_data.get('originChamberCode', ''),
            title=(bill_data.get('title', '') or '')[:200],
            bill_type=bill_data.get('type', ''),
            congress_url=bill_data.get('url', ''),
            introduced_date=parse_date(bill_data.get('introducedDate')),
            latest_action_date=parse_date(latest_action.get('actionDate')),
            latest_action_text=latest_action.get('text', ''),
            text='',  # We'll add text fetching later if needed
        )
        return bill

    def update_bill(self, bill, bill_data):
        """Update existing bill if changes detected"""
        latest_action = bill_data.get('latestAction', {})
        
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except:
                return None
        
        new_action_date = parse_date(latest_action.get('actionDate'))
        new_action_text = latest_action.get('text', '')
        
        updated = False
        
        # Check if action date is newer
        if new_action_date and (not bill.latest_action_date or new_action_date > bill.latest_action_date):
            bill.latest_action_date = new_action_date
            updated = True
        
        # Check if action text changed
        if new_action_text and new_action_text != bill.latest_action_text:
            bill.latest_action_text = new_action_text
            updated = True
        
        if updated:
            bill.save()
        
        return updated
