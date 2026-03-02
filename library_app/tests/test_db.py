from django.conf import settings
from django.test import SimpleTestCase


class DatabaseConfigTests(SimpleTestCase):
    def test_mysql_configuration_is_present(self):
        db = settings.DATABASES['default']
        self.assertEqual(db['ENGINE'], 'django.db.backends.mysql')
        self.assertEqual(db['NAME'], 'library_db')
        self.assertEqual(db['USER'], 'root')
        self.assertEqual(db['HOST'], 'localhost')
        self.assertEqual(db['PORT'], '3306')
