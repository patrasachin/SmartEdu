from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(model_name='attendance', old_name='class_name', new_name='department'),
        migrations.AlterField(model_name='attendance', name='department', field=models.CharField(max_length=100)),
        migrations.AddField(model_name='attendance', name='semester', field=models.PositiveSmallIntegerField(default=1)),
    ]
