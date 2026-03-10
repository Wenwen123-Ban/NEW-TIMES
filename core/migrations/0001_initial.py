# Generated manually for LBAS Django migration
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Book',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book_no', models.CharField(max_length=50, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('status', models.CharField(default='Available', max_length=30)),
                ('category', models.CharField(default='General', max_length=80)),
            ],
            options={'db_table': 'lbas_books'},
        ),
        migrations.CreateModel(
            name='DateRestriction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(unique=True)),
                ('action', models.CharField(max_length=10)),
                ('reason', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'db_table': 'lbas_date_restrictions'},
        ),
        migrations.CreateModel(
            name='HomeCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('card_id', models.IntegerField(unique=True)),
                ('title', models.CharField(blank=True, max_length=200)),
                ('body', models.TextField(blank=True)),
            ],
            options={'db_table': 'lbas_home_cards'},
        ),
        migrations.CreateModel(
            name='NewsPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('post_id', models.CharField(default=uuid.uuid4, max_length=64, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('summary', models.TextField()),
                ('body', models.TextField()),
                ('image_filename', models.CharField(blank=True, max_length=255, null=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('author', models.CharField(default='Admin', max_length=150)),
            ],
            options={'db_table': 'lbas_news'},
        ),
        migrations.CreateModel(
            name='RegistrationRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_id', models.CharField(max_length=100, unique=True)),
                ('request_number', models.CharField(blank=True, max_length=10)),
                ('name', models.CharField(max_length=150)),
                ('school_id', models.CharField(max_length=50)),
                ('year_level', models.CharField(max_length=10)),
                ('school_level', models.CharField(max_length=20)),
                ('course', models.CharField(blank=True, max_length=100)),
                ('password', models.CharField(max_length=255)),
                ('photo', models.CharField(default='default.png', max_length=255)),
                ('status', models.CharField(default='pending', max_length=20)),
                ('reviewed_by', models.CharField(blank=True, max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={'db_table': 'lbas_registration_requests'},
        ),
        migrations.CreateModel(
            name='SystemLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(max_length=50)),
                ('school_id', models.CharField(blank=True, max_length=50)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('month', models.CharField(max_length=7)),
            ],
            options={'db_table': 'lbas_logs'},
        ),
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book_no', models.CharField(max_length=50)),
                ('title', models.CharField(blank=True, max_length=255)),
                ('school_id', models.CharField(max_length=50)),
                ('borrower_name', models.CharField(blank=True, max_length=150)),
                ('status', models.CharField(max_length=30)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('expiry', models.DateField(blank=True, null=True)),
                ('return_date', models.DateTimeField(blank=True, null=True)),
                ('pickup_schedule', models.CharField(blank=True, max_length=30)),
                ('pickup_location', models.CharField(blank=True, max_length=100)),
                ('reservation_note', models.TextField(blank=True)),
                ('phone_number', models.CharField(blank=True, max_length=20)),
                ('contact_type', models.CharField(blank=True, max_length=10)),
                ('request_id', models.CharField(default=uuid.uuid4, max_length=100, unique=True)),
                ('approved_by', models.CharField(blank=True, max_length=100)),
            ],
            options={'db_table': 'lbas_transactions'},
        ),
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school_id', models.CharField(max_length=50, unique=True)),
                ('name', models.CharField(max_length=150)),
                ('password', models.CharField(max_length=255)),
                ('category', models.CharField(default='Student', max_length=50)),
                ('photo', models.CharField(default='default.png', max_length=255)),
                ('status', models.CharField(default='approved', max_length=20)),
                ('is_staff', models.BooleanField(default=False)),
                ('phone_number', models.CharField(blank=True, max_length=20)),
                ('year_level', models.CharField(blank=True, max_length=10)),
                ('school_level', models.CharField(blank=True, max_length=20)),
                ('course', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'lbas_users'},
        ),
    ]
