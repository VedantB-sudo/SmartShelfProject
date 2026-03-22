import os
import django
from django.core.management import call_command
from django.contrib.auth.models import User

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartshelf_project.settings')
django.setup()

def setup_app():
    # 1. Run migrations for the auth system
    call_command('migrate', '--noinput')
    
    # 2. Create superuser if it doesn't exist
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@smartshelf.com', 'SecurePassword123!')
        print("Superuser created successfully.")
    else:
        print("Superuser already exists.")

if __name__ == '__main__':
    setup_app()