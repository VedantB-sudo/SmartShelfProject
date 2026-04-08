import os
from django.core.wsgi import get_wsgi_application

# COMMENT OUT OR DELETE THESE TWO LINES:
# import pymysql
# pymysql.install_as_MySQLdb()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartshelf_project.settings')
application = get_wsgi_application()