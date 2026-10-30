from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assignments', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(model_name='assignment', old_name='class_name', new_name='department'),
        migrations.AlterField(model_name='assignment', name='department', field=models.CharField(verbose_name='Department', max_length=100, db_index=True)),
        migrations.AddField(model_name='assignment', name='semester', field=models.PositiveSmallIntegerField(default=1, verbose_name='Semester')),
    ]
