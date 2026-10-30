from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exams', '0002_exam_closes_at_alter_exam_class_name'),
    ]

    operations = [
        migrations.RenameField(model_name='exam', old_name='class_name', new_name='department'),
        migrations.AlterField(model_name='exam', name='department', field=models.CharField(verbose_name='Department', max_length=100)),
        migrations.AddField(model_name='exam', name='semester', field=models.PositiveSmallIntegerField(default=1, verbose_name='Semester')),
    ]
