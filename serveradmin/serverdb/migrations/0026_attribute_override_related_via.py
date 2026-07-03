from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0025_rename_serverbooleanattribute_attribute_server_bool_attribu_25fb6c_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='attribute',
            name='override_related_via',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Allow this attribute to be set directly even on '
                    'servertypes where it is configured as related via '
                    'another attribute.  Consistency between the direct '
                    'value and the related-via relation is enforced on '
                    'commit.'
                ),
            ),
        ),
    ]
