# # #!/bin/bash
# # set -e

# # echo "Installing dependencies..."
# # pip install -r requirements.txt

# # echo "Running migrations..."
# # python manage.py migrate

# # echo "Creating log directory..."
# # mkdir -p /tmp/logs

# # echo "Adding cron jobs..."
# # python manage.py crontab add

# # echo "Deployment setup complete."

# #!/bin/bash
# set -e

# echo "Installing dependencies..."
# pip install -r requirements.txt

# echo "Collecting static files..."
# python manage.py collectstatic --noinput

# echo "Running migrations..."
# python manage.py migrate --noinput

# echo "Creating log directory..."
# mkdir -p /tmp/logs

# echo "Adding cron jobs..."
# python manage.py crontab add

# echo "Starting gunicorn..."
# exec gunicorn --bind 0.0.0.0:8000 lumina_care.wsgi:application


# # #!/bin/bash
# # set -e

# # echo "Installing dependencies..."
# # pip install -r requirements.txt

# # echo "Running migrations..."
# # python manage.py migrate

# # echo "Creating log directory..."
# # mkdir -p /tmp/logs

# # echo "Adding cron jobs..."
# # python manage.py crontab add

# # echo "Deployment setup complete."

# #!/bin/bash
# set -e

# echo "Installing dependencies..."
# pip install -r requirements.txt

# echo "Collecting static files..."
# python manage.py collectstatic --noinput

# echo "Running migrations..."
# python manage.py migrate --noinput

# echo "Creating log directory..."
# mkdir -p /tmp/logs

# echo "Adding cron jobs..."
# python manage.py crontab add

# echo "Starting gunicorn..."
# exec gunicorn --bind 0.0.0.0:8000 lumina_care.wsgi:application
#!/bin/bash
set -e

# Ensure there is swap space


if ! swapon --show | grep -q '/swapfile'; then
    echo "No swap detected. Creating 2GB swap file..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo "Swap file created and enabled."
else
    echo "Swap already enabled. Skipping swap creation."
fi

echo "Installing dependencies..."
pip install -r requirements.txt --no-cache-dir

echo "Collecting static files..."
python3 manage.py collectstatic --noinput

echo "Running migrations..."
python3 manage.py migrate --noinput

echo "Creating log directory..."
mkdir -p /tmp/logs

echo "Adding cron jobs..."
python3 manage.py crontab add

echo "Starting gunicorn..."
exec gunicorn --bind 0.0.0.0:8000 lumina_care.wsgi:application
