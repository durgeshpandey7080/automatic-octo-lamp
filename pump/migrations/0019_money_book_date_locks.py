from django.db import migrations

SOURCES = {'moneyaccount': 'opening_date', 'moneytransfer': 'date', 'bankallocation': 'date'}


def install(apps, schema_editor):
    for name, field in SOURCES.items():
        for operation, refs in [('INSERT', ['NEW']), ('UPDATE', ['OLD', 'NEW']), ('DELETE', ['OLD'])]:
            condition = "EXISTS (SELECT 1 FROM pump_businessdayclose c WHERE c.status='CLOSED' AND (" + ' OR '.join('c.date >= ' + ref + '."' + field + '"' for ref in refs) + '))'
            schema_editor.execute('CREATE TRIGGER "closed_' + name + '_' + operation.lower() + '" BEFORE ' + operation + ' ON "pump_' + name + '" WHEN ' + condition + " BEGIN SELECT RAISE(ABORT, 'Business date is locked by an approved daily close'); END")


def uninstall(apps, schema_editor):
    for name in SOURCES:
        for operation in ['insert', 'update', 'delete']:
            schema_editor.execute('DROP TRIGGER IF EXISTS "closed_' + name + '_' + operation + '"')


class Migration(migrations.Migration):
    dependencies = [('pump', '0018_moneyaccount_bankallocation_moneytransfer_and_more')]
    operations = [migrations.RunPython(install, uninstall)]
