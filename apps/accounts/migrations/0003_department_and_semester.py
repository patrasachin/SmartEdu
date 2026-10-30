from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_studentprofile_guardian_email_and_more'),
    ]

    operations = [
        migrations.RenameField(model_name='studentprofile', old_name='class_name', new_name='department'),
        migrations.AlterField(model_name='studentprofile', name='department', field=models.CharField(verbose_name='Department', max_length=100, default='')),
        migrations.AddField(model_name='studentprofile', name='semester', field=models.PositiveSmallIntegerField(default=1, verbose_name='Semester')),
        migrations.RemoveField(model_name='studentprofile', name='section'),
    ]
