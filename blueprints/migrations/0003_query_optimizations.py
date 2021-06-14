# Generated by Django 3.1.10 on 2021-05-10 11:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blueprints", "0002_add_locations_permission"),
    ]

    operations = [
        migrations.AlterField(
            model_name="request",
            name="status",
            field=models.CharField(
                choices=[
                    ("OP", "Open"),
                    ("IP", "In Progress"),
                    ("FL", "Fulfilled"),
                    ("CL", "Cancelled"),
                ],
                db_index=True,
                help_text="Status of the blueprint request",
                max_length=2,
            ),
        ),
    ]
