# Generated by Django 5.2.2 on 2025-07-14 11:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('talent_engine', '0007_jobrequisition_branch_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='jobrequisition',
            name='status',
            field=models.CharField(choices=[('open', 'Open'), ('pending', 'Pending'), ('closed', 'Closed'), ('rejected', 'Rejected')], default='pending', max_length=20),
        ),
    ]
