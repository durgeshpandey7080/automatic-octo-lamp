from django.db import migrations


def install(apps,schema_editor):
    for op,refs in [('INSERT',['NEW']),('UPDATE',['OLD','NEW']),('DELETE',['OLD'])]:
        condition=' OR '.join("EXISTS (SELECT 1 FROM pump_businessdayclose c WHERE c.status='CLOSED' AND c.date>="+ref+'.date)' for ref in refs)
        schema_editor.execute('CREATE TRIGGER closed_salarypayment_'+op.lower()+' BEFORE '+op+' ON pump_salarypayment WHEN '+condition+" BEGIN SELECT RAISE(ABORT, 'Business date is locked by an approved daily close'); END")


def uninstall(apps,schema_editor):
    for op in ['insert','update','delete']:schema_editor.execute('DROP TRIGGER IF EXISTS closed_salarypayment_'+op)


class Migration(migrations.Migration):
    dependencies=[('pump','0027_salarypayment')]
    operations=[migrations.RunPython(install,uninstall)]
