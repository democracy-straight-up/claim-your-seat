# Congress API Sync Setup

Simple Django-based solution to sync Congress.gov API data three times a day.

## 🚀 Quick Start

### 1. Set your API key

```bash
export CONGRESS_API_KEY="your-api-key-here"
```

### 2. Test the setup

```bash
# Test API connection
python manage.py sync_congress --test

# Run sync manually
python manage.py sync_congress
```

### 3. Set up automatic syncing (3 times a day)

```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

## 📋 Manual Cron Setup

If you prefer to set up cron manually:

```bash
crontab -e
```

Add these lines:

```
# Congress API Sync - 3 times a day
0 8 * * * /path/to/your/env/bin/python /path/to/your/project/manage.py sync_congress >> /path/to/your/project/sync.log 2>&1
0 12 * * * /path/to/your/env/bin/python /path/to/your/project/manage.py sync_congress >> /path/to/your/project/sync.log 2>&1
0 20 * * * /path/to/your/env/bin/python /path/to/your/project/manage.py sync_congress >> /path/to/your/project/sync.log 2>&1
```

## 🔧 Command Options

```bash
# Test API connection only
python manage.py sync_congress --test

# Run full sync with default settings
python manage.py sync_congress

# Limit API requests (useful for testing)
python manage.py sync_congress --limit 50
```

## 📊 Django Admin Interface

1. Go to `/admin/bills/bill/`
2. Click on "Sync Congress Data" or "Test API Connection" buttons
3. Monitor the sync process through Django admin

## 📝 Logs

Sync logs are written to `sync.log` in your project directory:

```bash
# View recent logs
tail -f sync.log

# View all logs
cat sync.log
```

## 🎯 What it does

- Fetches all bills from Congress.gov API
- Filters for HR bills from Congress 119 only
- Checks for existing bills in database
- Creates new bills or updates existing ones if changes detected
- Fetches additional details like committees, actions, and text for each bill
- Runs three times a day: 8 AM, 12 PM, and 8 PM

## 🔍 Monitoring

Check if cron jobs are working:

```bash
# List current cron jobs
crontab -l

# Check sync logs
tail sync.log

# View Django admin for latest bills
# Go to /admin/bills/bill/
```

## ⚙️ Configuration

Environment variables:

- `CONGRESS_API_KEY`: Your Congress.gov API key (required)

## 📁 Files Created

- `bills/management/commands/sync_congress.py` - Main sync command
- `setup_cron.sh` - Cron setup helper script
- `sync.log` - Sync operation logs (created automatically)

## 🆘 Troubleshooting

1. **API connection fails**: Check your `CONGRESS_API_KEY`
2. **Cron jobs not running**: Check crontab with `crontab -l`
3. **Permission errors**: Make sure scripts are executable
4. **Database errors**: Check Django settings and run migrations

That's it! Simple Django-based solution with no Celery complexity.
