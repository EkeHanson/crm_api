# #!/bin/bash
# set -e

# echo "Installing dependencies..."
# pip install -r requirements.txt

# echo "Running migrations..."
# python manage.py migrate

# echo "Creating log directory..."
# mkdir -p /tmp/logs

# echo "Adding cron jobs..."
# python manage.py crontab add

# echo "Deployment setup complete."

#!/bin/bash
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate --noinput

echo "Creating log directory..."
mkdir -p /tmp/logs

echo "Adding cron jobs..."
python manage.py crontab add

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 lumina_care.wsgi:application
