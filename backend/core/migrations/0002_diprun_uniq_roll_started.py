from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="diprun",
            constraint=models.UniqueConstraint(
                fields=("roll", "started_at"), name="uniq_dip_roll_started"
            ),
        ),
    ]
