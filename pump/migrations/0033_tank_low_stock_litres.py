from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pump', '0032_shortage_date_locks')]
    operations = [migrations.AddField(
        model_name='tank', name='low_stock_litres',
        field=models.DecimalField(decimal_places=3, max_digits=12, default=Decimal('5000'),
            validators=[MinValueValidator(Decimal('0'))], verbose_name='Low stock warning (litres)'))]
