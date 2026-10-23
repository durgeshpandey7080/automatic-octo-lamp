from django.db import migrations


def install(apps, schema_editor):
    for operation, refs in [('INSERT', ['NEW']), ('UPDATE', ['OLD', 'NEW']), ('DELETE', ['OLD'])]:
        condition = "EXISTS (SELECT 1 FROM pump_businessdayclose c WHERE c.status='CLOSED' AND (" + ' OR '.join('c.date >= ' + ref + '.date' for ref in refs) + '))'
        schema_editor.execute('CREATE TRIGGER "closed_tankqualityobservation_' + operation.lower() + '" BEFORE ' + operation + ' ON pump_tankqualityobservation WHEN ' + condition + " BEGIN SELECT RAISE(ABORT, 'Business date is locked by an approved daily close'); END")


def uninstall(apps, schema_editor):
    for operation in ['insert', 'update', 'delete']:
        schema_editor.execute('DROP TRIGGER IF EXISTS "closed_tankqualityobservation_' + operation + '"')


class Migration(migrations.Migration):
    dependencies = [('pump', '0021_tankqualityobservation')]
    operations = [migrations.RunPython(install, uninstall)]
