from django.db import migrations


def install(apps,schema_editor):
    for op in ['UPDATE','DELETE']:
        schema_editor.execute(f"CREATE TRIGGER immutable_salary_adjustment_{op.lower()} BEFORE {op} ON pump_salaryshortageadjustment BEGIN SELECT RAISE(ABORT, 'Salary adjustments are append-only'); END")
    schema_editor.execute("""CREATE TRIGGER salary_adjustment_chain BEFORE INSERT ON pump_salaryshortageadjustment WHEN
        NEW.revised_amount < 0 OR NEW.revised_amount > (SELECT amount FROM pump_salarydeduction WHERE id=NEW.deduction_id)
        OR NEW.previous_amount != COALESCE((SELECT revised_amount FROM pump_salaryshortageadjustment WHERE deduction_id=NEW.deduction_id ORDER BY id DESC LIMIT 1),(SELECT amount FROM pump_salarydeduction WHERE id=NEW.deduction_id))
        BEGIN SELECT RAISE(ABORT, 'Invalid salary adjustment chain'); END""")
    for operation,refs in [('INSERT',['NEW']),('UPDATE',['OLD','NEW']),('DELETE',['OLD'])]:
        condition=' OR '.join("EXISTS (SELECT 1 FROM pump_businessdayclose c JOIN pump_shift s ON s.id="+ref+".shift_id WHERE c.status='CLOSED' AND c.date>=s.date)" for ref in refs)
        schema_editor.execute('CREATE TRIGGER closed_shiftdiscount_'+operation.lower()+' BEFORE '+operation+' ON pump_shiftdiscount WHEN '+condition+" BEGIN SELECT RAISE(ABORT, 'Business date is locked by an approved daily close'); END")


def uninstall(apps,schema_editor):
    for name in ['immutable_salary_adjustment_update','immutable_salary_adjustment_delete','salary_adjustment_chain','closed_shiftdiscount_insert','closed_shiftdiscount_update','closed_shiftdiscount_delete']:
        schema_editor.execute('DROP TRIGGER IF EXISTS '+name)


class Migration(migrations.Migration):
    dependencies=[('pump','0023_salaryshortageadjustment_shiftdiscount')]
    operations=[migrations.RunPython(install,uninstall)]
