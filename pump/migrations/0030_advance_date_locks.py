from django.db import migrations


def install(apps,schema_editor):
    for table in ['salaryadvance','advancerecovery']:
        for op,refs in [('INSERT',['NEW']),('UPDATE',['OLD','NEW']),('DELETE',['OLD'])]:
            condition=' OR '.join("EXISTS (SELECT 1 FROM pump_businessdayclose c WHERE c.status='CLOSED' AND c.date>="+ref+'.date)' for ref in refs)
            schema_editor.execute('CREATE TRIGGER closed_'+table+'_'+op.lower()+' BEFORE '+op+' ON pump_'+table+' WHEN '+condition+" BEGIN SELECT RAISE(ABORT, 'Business date is locked by an approved daily close'); END")


def uninstall(apps,schema_editor):
    for table in ['salaryadvance','advancerecovery']:
        for op in ['insert','update','delete']:schema_editor.execute('DROP TRIGGER IF EXISTS closed_'+table+'_'+op)


class Migration(migrations.Migration):
    dependencies=[('pump','0029_salaryadvance_advancerecovery_and_more')]
    operations=[migrations.RunPython(install,uninstall)]
