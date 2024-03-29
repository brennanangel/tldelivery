# Generated by Django 2.0.9 on 2018-10-13 19:36

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Delivery",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "order_number",
                    models.CharField(blank=True, max_length=20, null=True, unique=True),
                ),
                (
                    "recipient_last_name",
                    models.CharField(blank=True, max_length=40, null=True),
                ),
                (
                    "recipient_first_name",
                    models.CharField(blank=True, max_length=40, null=True),
                ),
                (
                    "recipient_phone_number",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "recipient_email",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "address_name",
                    models.CharField(
                        blank=True,
                        help_text="e.g., Company Name",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "address_line_1",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "address_line_2",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "address_city",
                    models.CharField(blank=True, max_length=40, null=True),
                ),
                (
                    "address_postal_code",
                    models.CharField(blank=True, max_length=10, null=True),
                ),
                ("notes", models.TextField(blank=True, null=True)),
            ],
            options={
                "verbose_name_plural": "Deliveries",
            },
        ),
        migrations.CreateModel(
            name="Item",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("item_name", models.CharField(max_length=255)),
                ("quantity", models.SmallIntegerField()),
                ("picked_up", models.BooleanField(default=False)),
                ("note", models.CharField(blank=True, max_length=255, null=True)),
                ("clover_id", models.CharField(blank=True, max_length=40, null=True)),
                (
                    "Delivery",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="delivery.Delivery",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Shift",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("date", models.DateField()),
                (
                    "time",
                    models.CharField(
                        choices=[("AM", "AM"), ("PM", "PM"), ("SP", "Special")],
                        max_length=2,
                    ),
                ),
                ("slots_available", models.SmallIntegerField(default=20)),
                ("comment", models.CharField(blank=True, max_length=255, null=True)),
                ("notes", models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="shift",
            unique_together={("date", "time")},
        ),
        migrations.AddField(
            model_name="delivery",
            name="delivery_shift",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="delivery.Shift"
            ),
        ),
    ]
