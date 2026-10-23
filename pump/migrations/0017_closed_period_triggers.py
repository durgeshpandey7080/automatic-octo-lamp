from django.db import migrations

SOURCES = {
    'Shift': ['date'], 'DailyFuelPrice': ['date'], 'Reading': ['shift__date'],
    'Handover': ['shift__date'], 'DebtorTransaction': ['date', 'shift__date'],
    'Expense': ['date', 'shift__date'], 'LubeSale': ['shift__date'],
    'TankOpening': ['date'], 'FuelDelivery': ['date'], 'TankDip': ['shift__date'],
    'Duty': ['date'], 'DutyAssignment': ['duty__date'], 'FuelTest': ['reading__shift__date'],
    'OtherIncome': ['date', 'shift__date'], 'DigitalCollection': ['shift__date'],
    'LubeMovement': ['date'], 'CashMovement': ['shift__date'],
    'BankReconciliation': ['settlement_date'],
    'SalesReceipt': ['reading__shift__date', 'lube_sale__shift__date'],
    'FuelPurchase': ['date', 'delivery__date'], 'SupplierPayment': ['date'], 'SupplierCredit': ['date'],
}


def date_sql(model, parts, reference, depth=0):
    field = model._meta.get_field(parts[0])
    if len(parts) == 1:
        return reference + '."' + field.column + '"'
    related = field.remote_field.model
    alias = 'r' + str(depth)
    expression = date_sql(related, parts[1:], alias, depth + 1)
    return '(SELECT ' + expression + ' FROM "' + related._meta.db_table + '" ' + alias + ' WHERE ' + alias + '."' + related._meta.pk.column + '" = ' + reference + '."' + field.column + '")'


def install(apps, schema_editor):
    if schema_editor.connection.vendor != 'sqlite':
        raise RuntimeError('Closed-period triggers currently require SQLite; port these guards before changing database engines.')
    for name, paths in SOURCES.items():
        model = apps.get_model('pump', name)
        for operation, refs in [('INSERT', ['NEW']), ('UPDATE', ['OLD', 'NEW']), ('DELETE', ['OLD'])]:
            comparisons = ['c.date >= ' + date_sql(model, path.split('__'), ref) for ref in refs for path in paths]
            condition = "EXISTS (SELECT 1 FROM pump_businessdayclose c WHERE c.status='CLOSED' AND (" + ' OR '.join(comparisons) + '))'
            schema_editor.execute('CREATE TRIGGER "closed_' + name.lower() + '_' + operation.lower() + '" BEFORE ' + operation + ' ON "' + model._meta.db_table + '" WHEN ' + condition + " BEGIN SELECT RAISE(ABORT, 'Business date is locked by an approved daily close'); END")


def uninstall(apps, schema_editor):
    for name in SOURCES:
        for operation in ['insert', 'update', 'delete']:
            schema_editor.execute('DROP TRIGGER IF EXISTS "closed_' + name.lower() + '_' + operation + '"')


class Migration(migrations.Migration):
    dependencies = [('pump', '0016_businessdayclose_staffaccess')]
    operations = [migrations.RunPython(install, uninstall)]
