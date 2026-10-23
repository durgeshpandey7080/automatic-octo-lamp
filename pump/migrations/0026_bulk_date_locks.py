from django.db import migrations


def install(apps,schema_editor):
    for operation,refs in [('INSERT',['NEW']),('UPDATE',['OLD','NEW']),('DELETE',['OLD'])]:
        condition=' OR '.join("EXISTS (SELECT 1 FROM pump_businessdayclose c JOIN pump_reading r ON r.id="+ref+".reading_id JOIN pump_shift s ON s.id=r.shift_id WHERE c.status='CLOSED' AND c.date>=s.date)" for ref in refs)
        schema_editor.execute('CREATE TRIGGER closed_bulksaleallocation_'+operation.lower()+' BEFORE '+operation+' ON pump_bulksaleallocation WHEN '+condition+" BEGIN SELECT RAISE(ABORT, 'Business date is locked by an approved daily close'); END")


def uninstall(apps,schema_editor):
    for op in ['insert','update','delete']:
        schema_editor.execute('DROP TRIGGER IF EXISTS closed_bulksaleallocation_'+op)


class Migration(migrations.Migration):
    dependencies=[('pump','0025_bulksaleallocation')]
    operations=[migrations.RunPython(install,uninstall)]
