from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('serverdb', '0026_attribute_override_related_via'),
    ]

    operations = [
        migrations.AddField(
            model_name='servertypeattribute',
            name='override_related_via',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Allow this attribute to be set directly on this '
                    'servertype even though it is configured as related via '
                    'another attribute.  Consistency between the direct value '
                    'and the related-via relation is enforced on commit.  '
                    'Only meaningful together with a related via attribute.'
                ),
            ),
        ),
        migrations.RemoveField(
            model_name='attribute',
            name='override_related_via',
        ),
    ]
