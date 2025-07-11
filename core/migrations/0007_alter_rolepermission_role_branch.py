# Generated by Django 5.2.2 on 2025-07-11 13:01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_merge_20250710_1011'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rolepermission',
            name='role',
            field=models.CharField(choices=[('admin', 'Admin'), ('hr', 'HR'), ('carer', 'Carer'), ('client', 'Client'), ('family', 'Family'), ('auditor', 'Auditor'), ('tutor', 'Tutor'), ('assessor', 'Assessor'), ('iqa', 'IQA'), ('eqa', 'EQA'), ('recruiter', 'Recruiter'), ('team_manager', 'Team Manager')], max_length=20),
        ),
        migrations.CreateModel(
            name='Branch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('location', models.CharField(blank=True, max_length=255)),
                ('is_head_office', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='branches', to='core.tenant')),
            ],
            options={
                'unique_together': {('tenant', 'name')},
            },
        ),
    ]
