from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Book',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('book_no', models.CharField(max_length=50, unique=True)),
                ('title', models.CharField(blank=True, max_length=255)),
                ('status', models.CharField(choices=[('Available', 'Available'), ('Reserved', 'Reserved'), ('Borrowed', 'Borrowed')], default='Available', max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name='ReservationTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('school_id', models.CharField(max_length=128)),
                ('status', models.CharField(choices=[('Reserved', 'Reserved'), ('Unavailable', 'Unavailable'), ('Cancelled', 'Cancelled'), ('Expired', 'Expired')], default='Reserved', max_length=20)),
                ('date', models.DateTimeField(default=django.utils.timezone.now)),
                ('expiry', models.DateTimeField(blank=True, null=True)),
                ('borrower_name', models.CharField(blank=True, max_length=255)),
                ('pickup_location', models.CharField(blank=True, max_length=255)),
                ('pickup_schedule', models.CharField(blank=True, max_length=50)),
                ('reservation_note', models.TextField(blank=True)),
                ('cancelled_at', models.DateTimeField(blank=True, null=True)),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to='library.book')),
            ],
        ),
        migrations.AddIndex(
            model_name='reservationtransaction',
            index=models.Index(fields=['school_id', 'status'], name='library_res_school__f35691_idx'),
        ),
        migrations.AddIndex(
            model_name='reservationtransaction',
            index=models.Index(fields=['book', 'status'], name='library_res_book_id_bcccb5_idx'),
        ),
    ]
