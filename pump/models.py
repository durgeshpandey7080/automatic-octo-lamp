from decimal import Decimal, ROUND_HALF_UP
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.db.models.functions import Round

def meter(**kwargs):
    return models.DecimalField(max_digits=16, decimal_places=3,
        validators=[MinValueValidator(Decimal('0'))], **kwargs)

class Tank(models.Model):
    name = models.CharField(max_length=60, unique=True)
    fuel = models.CharField(max_length=10, choices=[('PETROL', 'Petrol'), ('DIESEL', 'Diesel')])
    capacity_litres = models.DecimalField(max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))])
    low_stock_litres = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('5000'),
        validators=[MinValueValidator(Decimal('0'))], verbose_name='Low stock warning (litres)')
    def __str__(self):
        return f'{self.name} ({self.get_fuel_display()})'

class Nozzle(models.Model):
    number = models.PositiveSmallIntegerField(unique=True,
        validators=[MinValueValidator(1), MaxValueValidator(8)])
    tank = models.ForeignKey(Tank, on_delete=models.PROTECT)
    class Meta:
        ordering = ['number']
        constraints = [models.CheckConstraint(condition=models.Q(number__gte=1, number__lte=8), name='nozzle_1_to_8')]
    def __str__(self):
        return f'Nozzle {self.number} - {self.tank.get_fuel_display()}'

class Shift(models.Model):
    date = models.DateField(default=timezone.localdate)
    number = models.PositiveSmallIntegerField(choices=[(1, 'Shift 1'), (2, 'Shift 2')])
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-date', '-number']
        constraints = [models.UniqueConstraint(fields=['date', 'number'], name='one_shift_per_slot'),
            models.CheckConstraint(condition=models.Q(number__in=[1, 2]), name='two_shifts_only')]
    def clean(self):
        if self.date and self.date > timezone.localdate():
            raise ValidationError({'date': 'Future shifts are not allowed.'})
    def __str__(self):
        return f'{self.date} / Shift {self.number}'

class Salesperson(models.Model):
    name = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class DailyFuelPrice(models.Model):
    date = models.DateField()
    fuel = models.CharField(max_length=10, choices=Tank._meta.get_field('fuel').choices)
    price_per_litre = models.DecimalField(max_digits=8, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))])

    class Meta:
        ordering = ['-date', 'fuel']
        constraints = [models.UniqueConstraint(fields=['date', 'fuel'], name='one_daily_fuel_price'),
            models.CheckConstraint(condition=models.Q(price_per_litre__gt=0), name='positive_fuel_price')]

    def __str__(self):
        return f'{self.date} / {self.get_fuel_display()} / Rs {self.price_per_litre}'


class Reading(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name='readings')
    nozzle = models.ForeignKey(Nozzle, on_delete=models.PROTECT)
    opening_litres = meter()
    closing_litres = meter()
    testing_litres = meter(default=Decimal('0.000'))
    returned_test_litres = meter(default=Decimal('0.000'))
    # Historical counters only. New entries use litres and the saved daily rate.
    opening_rupees = meter(null=True, blank=True)
    closing_rupees = meter(null=True, blank=True)
    # Nullable only to preserve readings recorded before salesperson/rate tracking.
    salesperson = models.ForeignKey(Salesperson, on_delete=models.PROTECT, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.001'))])
    class Meta:
        ordering = ['nozzle__number']
        constraints = [models.UniqueConstraint(fields=['shift', 'nozzle'], name='one_reading_per_nozzle_shift'),
            models.CheckConstraint(condition=models.Q(opening_litres__gte=0, opening_rupees__gte=0,
                closing_litres__gte=models.F('opening_litres'), closing_rupees__gte=models.F('opening_rupees')),
                name='nonnegative_increasing_meters'),
            models.CheckConstraint(condition=models.Q(unit_price__isnull=True) | models.Q(unit_price__gt=0),
                name='positive_reading_price')]
    def clean(self):
        errors = {}
        if self.opening_litres is not None and self.closing_litres is not None and (self.testing_litres < 0 or self.returned_test_litres < 0 or self.returned_test_litres > self.testing_litres or self.testing_litres > self.closing_litres - self.opening_litres):
            errors['__all__'] = 'Testing must fit dispensed litres; returned testing cannot exceed testing.'
        for unit in ['litres', 'rupees']:
            start, end = getattr(self, 'opening_' + unit), getattr(self, 'closing_' + unit)
            if start is not None and end is not None and end < start:
                errors['closing_' + unit] = 'Closing must be at least opening; meter resets are not supported.'
        if errors:
            raise ValidationError(errors)
    @property
    def litres_sold(self):
        return self.closing_litres - self.opening_litres - self.testing_litres
    @property
    def rupees_sold(self):
        if self.opening_rupees is None or self.closing_rupees is None:
            return None
        return self.closing_rupees - self.opening_rupees
    @property
    def expected_amount(self):
        if self.unit_price is None:
            return None
        return (self.litres_sold * self.unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    @property
    def meter_difference(self):
        if self.expected_amount is None or self.rupees_sold is None:
            return None
        return self.rupees_sold - self.expected_amount
    def __str__(self):
        return f'{self.shift} / {self.nozzle}'


class ManagerProfile(models.Model):
    name = models.CharField(max_length=100, unique=True)
    phone = models.CharField(max_length=25, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


def money():
    return models.DecimalField(max_digits=22, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))])


class Handover(models.Model):
    number = models.CharField(max_length=100,unique=True,null=True,blank=True)
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name='handovers')
    salesperson = models.ForeignKey(Salesperson, on_delete=models.PROTECT, related_name='handovers')
    submitted_to = models.ForeignKey(ManagerProfile, on_delete=models.PROTECT, related_name='handovers',
        verbose_name='Cash submitted to')
    cash_adjustment = models.DecimalField(max_digits=22,decimal_places=2,default=Decimal('0.00'))
    expected_sales = money()
    cash_received = money()
    card = money()
    upi = money()
    # Original unsplit UPI remains for historical receipts only.
    paytm_business = money()
    phonepe_business = money()
    credit_sales = money()
    expenses = money()
    notes = models.CharField(max_length=1000, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-shift__date', '-shift__number', 'salesperson__name']
        constraints = [
            models.UniqueConstraint(fields=['shift', 'salesperson'], name='one_handover_per_person_shift'),
            models.CheckConstraint(condition=models.Q(expected_sales__gte=0, cash_received__gte=0,
                card__gte=0, upi__gte=0, paytm_business__gte=0, phonepe_business__gte=0,
                credit_sales__gte=0, expenses__gte=0), name='nonnegative_handover_amounts'),
            models.CheckConstraint(condition=models.Q(expected_sales__gte=Round(models.F('card') + models.F('upi') +
                models.F('paytm_business') + models.F('phonepe_business') + models.F('credit_sales') +
                models.F('expenses'), precision=2)), name='handover_adjustments_within_sales'),
        ]

    @property
    def total_upi(self):
        return self.upi + self.paytm_business + self.phonepe_business

    @property
    def expected_cash(self):
        return self.expected_sales - self.card - self.total_upi - self.credit_sales - self.expenses + self.cash_adjustment

    @property
    def variance(self):
        return self.cash_received - self.expected_cash

    @property
    def difference_amount(self):
        return abs(self.variance)

    @property
    def status(self):
        if self.variance < 0:
            return 'Shortage'
        if self.variance > 0:
            return 'Excess'
        return 'Balanced'

    @property
    def total_collections(self):
        # Credit sales and expenses are adjustments, not money received.
        return self.cash_received + self.card + self.total_upi

    def clean(self):
        super().clean()
        amounts = [self.expected_sales, self.cash_received, self.card, self.upi,
            self.paytm_business, self.phonepe_business, self.credit_sales, self.expenses]
        if any(value is None or not value.is_finite() for value in amounts):
            raise ValidationError('Enter a valid amount in every collection field; use 0 where needed.')
        if self.expected_cash < 0:
            raise ValidationError('Card + Paytm for Business + PhonePe Business + earlier UPI + credit sales + expenses cannot exceed recorded sales.')
        if (self.credit_sales > 0 or self.expenses > 0 or self.variance != 0) and not self.notes.strip():
            raise ValidationError({'notes': 'Add credit/expense references and explain any shortage or excess.'})

    def __str__(self):
        return f'{self.shift} / {self.salesperson} / {self.status}'


class Debtor(models.Model):
    name = models.CharField(max_length=100, unique=True)
    phone = models.CharField(max_length=25, blank=True)
    address = models.CharField(max_length=300, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    @property
    def balance(self):
        return sum((entry.signed_amount for entry in self.transactions.all()), Decimal('0.00'))

    def __str__(self):
        return self.name


def positive_money():
    return models.DecimalField(max_digits=22, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))])


class DebtorTransaction(models.Model):
    KINDS = [('OPENING', 'Opening balance'), ('SALE', 'Credit sale'), ('PAYMENT', 'Repayment')]
    METHODS = [('CASH', 'Cash'), ('CARD', 'Card'), ('PAYTM', 'Paytm for Business'),
        ('PHONEPE', 'PhonePe Business'), ('BANK', 'Bank transfer')]
    debtor = models.ForeignKey(Debtor, on_delete=models.PROTECT, related_name='transactions')
    vehicle_number = models.CharField(max_length=30, blank=True)
    fuel_product = models.CharField(max_length=10, blank=True, choices=[('PETROL','Petrol'),('DIESEL','Diesel')])
    quantity = models.DecimalField(max_digits=16,decimal_places=3,null=True,blank=True,validators=[MinValueValidator(Decimal('0.001'))])
    saved_rate = models.DecimalField(max_digits=12,decimal_places=3,null=True,blank=True,validators=[MinValueValidator(Decimal('0.001'))])
    kind = models.CharField(max_length=10, choices=KINDS)
    date = models.DateField(default=timezone.localdate)
    amount = positive_money()
    reference = models.CharField(max_length=100, unique=True)
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, null=True, blank=True)
    salesperson = models.ForeignKey(Salesperson, on_delete=models.PROTECT, null=True, blank=True)
    payment_method = models.CharField(max_length=10, choices=METHODS, blank=True)
    received_by = models.ForeignKey(ManagerProfile, on_delete=models.PROTECT, null=True, blank=True,
        related_name='debtor_receipts')
    notes = models.CharField(max_length=1000, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'created_at', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='positive_debtor_amount'),
            models.UniqueConstraint(fields=['debtor'], condition=models.Q(kind='OPENING'), name='one_opening_per_debtor'),
            models.CheckConstraint(condition=(
                models.Q(kind='SALE', shift__isnull=False, salesperson__isnull=False,
                    payment_method='', received_by__isnull=True) |
                (models.Q(kind='PAYMENT', shift__isnull=True, salesperson__isnull=True,
                    received_by__isnull=False) & models.Q(payment_method__in=['CASH', 'CARD', 'PAYTM', 'PHONEPE', 'BANK'])) |
                models.Q(kind='OPENING', shift__isnull=True, salesperson__isnull=True,
                    payment_method='', received_by__isnull=True)), name='valid_debtor_entry_type')]

    @property
    def signed_amount(self):
        return -self.amount if self.kind == 'PAYMENT' else self.amount

    def clean(self):
        super().clean()
        if self.date and self.date > timezone.localdate():
            raise ValidationError({'date': 'Future entries are not allowed.'})
        if self.kind == 'SALE' and (not self.shift_id or not self.salesperson_id):
            raise ValidationError('Credit fuel sales require a recorded shift and its salesperson.')
        if self.kind == 'PAYMENT' and (not self.received_by_id or not self.payment_method):
            raise ValidationError('Repayments require a payment method and receiving manager.')

    def __str__(self):
        return f'{self.debtor} / {self.get_kind_display()} / Rs {self.amount}'


class Expense(models.Model):
    SOURCES = [('SHIFT_CASH', 'Salesperson shift cash'), ('STATION_CASH', 'Station cash'),
        ('BANK', 'Bank transfer'), ('PAYTM', 'Paytm for Business'), ('PHONEPE', 'PhonePe Business')]
    CATEGORIES = [('MAINTENANCE', 'Maintenance'), ('UTILITIES', 'Utilities'), ('STAFF', 'Staff'),
        ('SUPPLIES', 'Supplies'), ('TRANSPORT', 'Transport'), ('OTHER', 'Other')]
    date = models.DateField(default=timezone.localdate)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    description = models.CharField(max_length=200)
    payee = models.CharField(max_length=100, blank=True)
    voucher = models.CharField(max_length=100, unique=True)
    amount = positive_money()
    source = models.CharField(max_length=20, choices=SOURCES, default='SHIFT_CASH')
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, null=True, blank=True)
    salesperson = models.ForeignKey(Salesperson, on_delete=models.PROTECT, null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='positive_expense_amount'),
            models.CheckConstraint(condition=(
                models.Q(source='SHIFT_CASH', shift__isnull=False, salesperson__isnull=False) |
                models.Q(source__in=['STATION_CASH', 'BANK', 'PAYTM', 'PHONEPE'],
                    shift__isnull=True, salesperson__isnull=True)), name='expense_source_link')]

    def clean(self):
        super().clean()
        if self.date and self.date > timezone.localdate():
            raise ValidationError({'date': 'Future expenses are not allowed.'})
        if self.source == 'SHIFT_CASH':
            if not self.shift_id or not self.salesperson_id:
                raise ValidationError('Choose the recorded shift and salesperson whose cash paid the expense.')
            if self.date != self.shift.date:
                raise ValidationError({'date': 'A shift-cash expense must use that shift\'s business date.'})
        elif self.shift_id or self.salesperson_id:
            raise ValidationError('For station cash, bank, Paytm or PhonePe expenses, leave shift and salesperson blank.')

    def __str__(self):
        return f'{self.date} / {self.voucher} / Rs {self.amount}'


class LubeProduct(models.Model):
    inventory_started_at = models.DateTimeField(null=True,blank=True)
    reorder_level = models.DecimalField(max_digits=12,decimal_places=3,default=Decimal('0'),validators=[MinValueValidator(Decimal('0'))])
    UNITS = [('BOTTLE', 'Bottle'), ('CAN', 'Can'), ('PIECE', 'Piece'), ('LITRE', 'Litre'), ('PACK', 'Pack')]
    name = models.CharField(max_length=150, unique=True)
    unit = models.CharField(max_length=10, choices=UNITS, default='BOTTLE')
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        constraints = [models.CheckConstraint(condition=models.Q(selling_price__gt=0), name='positive_lube_product_rate')]

    def __str__(self):
        return f'{self.name} ({self.get_unit_display()})'


class LubeSale(models.Model):
    product = models.ForeignKey(LubeProduct, on_delete=models.PROTECT, related_name='sales')
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name='lube_sales')
    salesperson = models.ForeignKey(Salesperson, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    reference = models.CharField(max_length=100, unique=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-shift__date', '-shift__number', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(quantity__gt=0, unit_price__gt=0), name='positive_lube_sale')]

    @property
    def amount(self):
        return (self.quantity * self.unit_price).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def __str__(self):
        return f'{self.shift} / {self.product} / Rs {self.amount}'


class SalaryRecord(models.Model):
    salesperson = models.ForeignKey(Salesperson, on_delete=models.PROTECT)
    month = models.DateField(help_text='First day of salary month')
    base_salary = money()
    shortage_deduction = money()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-month', 'salesperson__name']
        constraints = [models.UniqueConstraint(fields=['salesperson', 'month'], name='one_salary_per_person_month'),
            models.CheckConstraint(condition=models.Q(base_salary__gte=models.F('shortage_deduction'), shortage_deduction__gte=0), name='salary_covers_shortage')]

    @property
    def net_salary(self):
        return self.base_salary - self.shortage_deduction

    @property
    def adjustment_credit(self):
        return sum((a.salary_credit for d in self.deductions.all() for a in d.adjustments.all()), Decimal('0.00'))

    @property
    def adjusted_net_salary(self):
        return self.net_salary + self.adjustment_credit + self.shortage_recovery_credit

    @property
    def shortage_recovery_credit(self):
        return sum((r.amount for r in self.shortage_receipts.all() if not r.voided), Decimal('0.00'))

    @property
    def paid_amount(self):
        return sum((p.amount for p in self.payments.all() if not p.voided), Decimal('0.00'))

    @property
    def advance_applied(self):
        return sum((a.amount for a in self.advance_recoveries.all() if not a.voided), Decimal('0.00'))

    @property
    def outstanding_salary(self):
        return self.adjusted_net_salary - self.paid_amount - self.advance_applied


class SalaryDeduction(models.Model):
    salary = models.ForeignKey(SalaryRecord, on_delete=models.PROTECT, related_name='deductions')
    handover = models.OneToOneField(Handover, on_delete=models.PROTECT, related_name='salary_deduction')
    amount = positive_money()


class TankOpening(models.Model):
    tank = models.OneToOneField(Tank, on_delete=models.PROTECT, related_name='stock_opening')
    date = models.DateField(help_text='Stock at the start of this business date, before sales and deliveries')
    litres = meter()
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class FuelDelivery(models.Model):
    number = models.CharField(max_length=100,unique=True,null=True,blank=True)
    tank = models.ForeignKey(Tank, on_delete=models.PROTECT, related_name='deliveries')
    date = models.DateField()
    litres = models.DecimalField(max_digits=16, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    invoice = models.CharField(max_length=100, unique=True)
    supplier = models.CharField(max_length=100)
    notes = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-date', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(litres__gt=0), name='positive_fuel_delivery')]

class TankDip(models.Model):
    tank = models.ForeignKey(Tank, on_delete=models.PROTECT, related_name='dips')
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT)
    physical_litres = meter()
    expected_litres = models.DecimalField(max_digits=18, decimal_places=3)
    notes = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-shift__date', '-pk']
        constraints = [models.UniqueConstraint(fields=['tank','shift'], name='one_dip_per_tank_close')]
    @property
    def variance(self):
        return self.physical_litres - self.expected_litres


class AuditEvent(models.Model):
    action = models.CharField(max_length=80)
    model_name = models.CharField(max_length=80)
    object_id = models.PositiveIntegerField()
    reason = models.CharField(max_length=500)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-created_at','-pk']

class Duty(models.Model):
    cancelled = models.BooleanField(default=False)
    date = models.DateField()
    number = models.PositiveSmallIntegerField(choices=[(1,'Shift 1'),(2,'Shift 2')])
    petrol_price = models.DecimalField(max_digits=8,decimal_places=3)
    diesel_price = models.DecimalField(max_digits=8,decimal_places=3)
    closed_shift = models.OneToOneField(Shift,on_delete=models.PROTECT,null=True,blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['date','number'],condition=models.Q(cancelled=False),name='one_duty_slot')]
    def __str__(self):
        return f'{self.date} / Duty {self.number}'

class DutyAssignment(models.Model):
    duty = models.ForeignKey(Duty,on_delete=models.PROTECT,related_name='assignments')
    nozzle = models.ForeignKey(Nozzle,on_delete=models.PROTECT)
    salesperson = models.ForeignKey(Salesperson,on_delete=models.PROTECT)
    opening_litres = meter()
    class Meta:
        ordering=['nozzle__number']
        constraints=[models.UniqueConstraint(fields=['duty','nozzle'],name='one_duty_nozzle')]

class FuelTest(models.Model):
    reading = models.ForeignKey(Reading,on_delete=models.PROTECT,related_name='tests')
    litres = models.DecimalField(max_digits=16,decimal_places=3,validators=[MinValueValidator(Decimal('0.001'))])
    disposition = models.CharField(max_length=10,choices=[('RETURNED','Returned to same tank'),('CONSUMED','Consumed / disposed')])
    reference = models.CharField(max_length=100,unique=True)
    reason = models.CharField(max_length=500)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class OtherIncome(models.Model):
    date = models.DateField()
    shift = models.ForeignKey(Shift,on_delete=models.PROTECT)
    salesperson = models.ForeignKey(Salesperson,on_delete=models.PROTECT)
    description = models.CharField(max_length=200)
    amount = positive_money()
    reference = models.CharField(max_length=100,unique=True)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class DigitalCollection(models.Model):
    number = models.CharField(max_length=100,unique=True,null=True,blank=True)
    shift = models.ForeignKey(Shift,on_delete=models.PROTECT)
    salesperson = models.ForeignKey(Salesperson,on_delete=models.PROTECT)
    method = models.CharField(max_length=10,choices=[('CARD','Card / POS'),('PAYTM','Paytm for Business'),('PHONEPE','PhonePe Business')])
    amount = positive_money()
    reference = models.CharField(max_length=100,unique=True)
    terminal = models.CharField(max_length=100,blank=True,help_text='Merchant/terminal identifier; no credentials')
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class LubeMovement(models.Model):
    supplier_invoice = models.CharField(max_length=100,blank=True)
    product = models.ForeignKey(LubeProduct,on_delete=models.PROTECT,related_name='movements')
    date = models.DateField()
    kind = models.CharField(max_length=10,choices=[('OPENING','Opening stock'),('PURCHASE','Purchase receipt'),('WASTAGE','Wastage'),('ADJUST_IN','Stock adjustment in'),('ADJUST_OUT','Stock adjustment out')])
    quantity = models.DecimalField(max_digits=12,decimal_places=3,validators=[MinValueValidator(Decimal('0'))])
    unit_cost = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal('0'),validators=[MinValueValidator(Decimal('0'))])
    reference = models.CharField(max_length=100,unique=True)
    supplier = models.CharField(max_length=100,blank=True)
    notes = models.CharField(max_length=500,blank=True)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class CashMovement(models.Model):
    shift = models.ForeignKey(Shift,on_delete=models.PROTECT)
    salesperson = models.ForeignKey(Salesperson,on_delete=models.PROTECT)
    manager = models.ForeignKey(ManagerProfile,on_delete=models.PROTECT)
    kind = models.CharField(max_length=10,choices=[('FLOAT','Opening cash float'),('OFFICE_IN','Cash received from office'),('RETURN','Cash returned to manager')])
    amount = positive_money()
    reference = models.CharField(max_length=100,unique=True)
    notes = models.CharField(max_length=500,blank=True)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class BankReconciliation(models.Model):
    voided = models.BooleanField(default=False)
    collection = models.ForeignKey(DigitalCollection,on_delete=models.PROTECT,related_name='reconciliations')
    settlement_date = models.DateField()
    bank_name = models.CharField(max_length=100)
    bank_reference = models.CharField(max_length=100,unique=True)
    net_received = money()
    fee = money()
    notes = models.CharField(max_length=500,blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['collection'],condition=models.Q(voided=False),name='one_active_bank_match')]

class SalesReceipt(models.Model):
    number = models.CharField(max_length=100,unique=True)
    reading = models.ForeignKey(Reading,on_delete=models.PROTECT,null=True,blank=True)
    lube_sale = models.ForeignKey(LubeSale,on_delete=models.PROTECT,null=True,blank=True)
    customer_name = models.CharField(max_length=100)
    vehicle_number = models.CharField(max_length=30,blank=True)
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=16,decimal_places=3)
    rate = models.DecimalField(max_digits=12,decimal_places=3)
    amount = positive_money()
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(reading__isnull=False,lube_sale__isnull=True)|models.Q(reading__isnull=True,lube_sale__isnull=False)),name='receipt_one_source'), models.UniqueConstraint(fields=['lube_sale'],condition=models.Q(voided=False,lube_sale__isnull=False),name='one_active_lube_receipt')]


class NumberSeries(models.Model):
    key = models.CharField(max_length=40,unique=True)
    last_number = models.PositiveIntegerField(default=0)


class Supplier(models.Model):
    name = models.CharField(max_length=120,unique=True)
    phone = models.CharField(max_length=30,blank=True)
    address = models.CharField(max_length=500,blank=True)
    active = models.BooleanField(default=True)
    class Meta:
        ordering=['name']
    def __str__(self):return self.name
    @property
    def outstanding(self):
        return sum((p.outstanding for p in self.purchases.filter(voided=False)),Decimal('0.00'))

class FuelPurchase(models.Model):
    number = models.CharField(max_length=100,unique=True)
    supplier = models.ForeignKey(Supplier,on_delete=models.PROTECT,related_name='purchases')
    delivery = models.ForeignKey(FuelDelivery,on_delete=models.PROTECT,related_name='purchases')
    date = models.DateField()
    supplier_invoice = models.CharField(max_length=100)
    invoiced_litres = models.DecimalField(max_digits=16,decimal_places=3,validators=[MinValueValidator(Decimal('0.001'))])
    unit_cost = models.DecimalField(max_digits=12,decimal_places=4,validators=[MinValueValidator(Decimal('0.0001'))])
    freight = money()
    notes = models.CharField(max_length=500,blank=True)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-date','-pk']
        constraints=[models.UniqueConstraint(fields=['supplier','supplier_invoice'],condition=models.Q(voided=False),name='unique_active_supplier_invoice'),
            models.UniqueConstraint(fields=['delivery'],condition=models.Q(voided=False),name='one_active_purchase_per_delivery')]
    def __str__(self):return self.number
    @property
    def fuel_cost(self):return (self.invoiced_litres*self.unit_cost).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    @property
    def total(self):return self.fuel_cost+self.freight
    @property
    def paid(self):return sum((p.amount for p in self.payments.filter(voided=False)),Decimal('0.00'))
    @property
    def credits(self):return sum((c.amount for c in self.credit_notes.filter(voided=False)),Decimal('0.00'))
    @property
    def outstanding(self):return self.total-self.paid-self.credits
    @property
    def delivery_variance(self):return self.delivery.litres-self.invoiced_litres

class SupplierPayment(models.Model):
    METHODS=[('CASH','Station cash'),('BANK','Bank transfer'),('PAYTM','Paytm for Business'),('PHONEPE','PhonePe Business'),('CARD','Card')]
    number=models.CharField(max_length=100,unique=True)
    purchase=models.ForeignKey(FuelPurchase,on_delete=models.PROTECT,related_name='payments')
    date=models.DateField()
    amount=positive_money()
    method=models.CharField(max_length=10,choices=METHODS)
    external_reference=models.CharField(max_length=100,blank=True)
    notes=models.CharField(max_length=500,blank=True)
    voided=models.BooleanField(default=False)
    recorded_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-date','-pk']
        constraints=[models.UniqueConstraint(fields=['method','external_reference'],condition=models.Q(voided=False)&~models.Q(external_reference=''),name='unique_active_supplier_transfer')]

class SupplierCredit(models.Model):
    number=models.CharField(max_length=100,unique=True)
    purchase=models.ForeignKey(FuelPurchase,on_delete=models.PROTECT,related_name='credit_notes')
    date=models.DateField()
    supplier_credit_reference=models.CharField(max_length=100)
    amount=positive_money()
    reason=models.CharField(max_length=500)
    voided=models.BooleanField(default=False)
    recorded_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-date','-pk']
        constraints=[models.UniqueConstraint(fields=['purchase','supplier_credit_reference'],condition=models.Q(voided=False),name='unique_active_supplier_credit')]


class StaffAccess(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='station_access')
    role = models.CharField(max_length=12, choices=[('CASHIER', 'Cashier'), ('MANAGER', 'Manager'), ('ACCOUNTANT', 'Accountant'), ('VIEWER', 'Viewer')])
    active = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.user} / {self.get_role_display()}'


class BusinessDayClose(models.Model):
    date = models.DateField(unique=True)
    status = models.CharField(max_length=12, default='DRAFT', choices=[('DRAFT', 'Draft'), ('SUBMITTED', 'Submitted'), ('REVIEWED', 'Reviewed'), ('CLOSED', 'Closed')])
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='submitted_days')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='reviewed_days')
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='closed_days')
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    snapshot = models.JSONField(default=dict)
    fingerprint = models.CharField(max_length=64, blank=True)
    exception_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.date} / {self.status}'


class MoneyAccount(models.Model):
    name = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=8, choices=[('CASH', 'Station cash'), ('BANK', 'Bank account')])
    opening_date = models.DateField()
    opening_balance = models.DecimalField(max_digits=16, decimal_places=2)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['kind'], condition=models.Q(kind='CASH'), name='one_station_cash_pool')]

    def __str__(self):
        return self.name


class MoneyTransfer(models.Model):
    number = models.CharField(max_length=100, unique=True)
    date = models.DateField()
    source = models.ForeignKey(MoneyAccount, on_delete=models.PROTECT, related_name='transfers_out')
    destination = models.ForeignKey(MoneyAccount, on_delete=models.PROTECT, related_name='transfers_in')
    amount = positive_money()
    external_reference = models.CharField(max_length=100)
    notes = models.CharField(max_length=500)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=~models.Q(source=models.F('destination')), name='transfer_different_accounts'),
            models.UniqueConstraint(fields=['external_reference'], condition=models.Q(voided=False), name='one_active_money_transfer_reference')]


class BankAllocation(models.Model):
    KINDS = [('SETTLEMENT', 'Digital settlement'), ('EXPENSE', 'Bank-paid expense'), ('DEBTOR', 'Debtor bank repayment'), ('SUPPLIER', 'Supplier bank payment')]
    kind = models.CharField(max_length=12, choices=KINDS)
    source_id = models.PositiveIntegerField()
    date = models.DateField()
    account = models.ForeignKey(MoneyAccount, on_delete=models.PROTECT)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['kind', 'source_id'], name='one_account_per_bank_source')]


class PaymentImportBatch(models.Model):
    provider = models.CharField(max_length=8, choices=[('PAYTM', 'Paytm Business'), ('PHONEPE', 'PhonePe Business')])
    merchant = models.CharField(max_length=100)
    checksum = models.CharField(max_length=64)
    new_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'merchant', 'checksum'], name='one_provider_file_import')]


class PaymentEvidence(models.Model):
    batch = models.ForeignKey(PaymentImportBatch, on_delete=models.PROTECT)
    provider = models.CharField(max_length=8, choices=PaymentImportBatch._meta.get_field('provider').choices)
    merchant = models.CharField(max_length=100)
    reference = models.CharField(max_length=100)
    date = models.DateField()
    amount = positive_money()
    description = models.CharField(max_length=200, blank=True)
    collection = models.OneToOneField(DigitalCollection, on_delete=models.PROTECT, null=True, blank=True)
    matched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    matched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'merchant', 'reference'], name='one_provider_transaction_evidence')]


class TankQualityObservation(models.Model):
    tank = models.ForeignKey(Tank, on_delete=models.PROTECT)
    date = models.DateField()
    kind = models.CharField(max_length=10, choices=[('MORNING', 'Morning observation'), ('DELIVERY', 'After delivery observation')])
    delivery = models.ForeignKey(FuelDelivery, on_delete=models.PROTECT, null=True, blank=True)
    observed_at = models.DateTimeField()
    observed_density = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    temperature_c = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('-50')), MaxValueValidator(Decimal('100'))])
    density_15c = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01'))])
    correction_source = models.CharField(max_length=200, blank=True)
    water_mm = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    notes = models.CharField(max_length=500, blank=True)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-observed_at']
        constraints = [models.UniqueConstraint(fields=['tank', 'date'], condition=models.Q(kind='MORNING', voided=False), name='one_active_morning_observation'),
            models.UniqueConstraint(fields=['delivery'], condition=models.Q(kind='DELIVERY', voided=False), name='one_active_delivery_observation')]

    def clean(self):
        if self.date and self.date > timezone.localdate():
            raise ValidationError('Future observation dates are not allowed.')
        if self.observed_at and (self.observed_at > timezone.now() or timezone.localtime(self.observed_at).date() != self.date):
            raise ValidationError('Observed time must be on the selected business date and cannot be in the future.')
        if self.kind == 'DELIVERY':
            if not self.delivery_id or self.delivery.tank_id != self.tank_id or self.delivery.date != self.date:
                raise ValidationError('Choose a delivery for this tank and business date.')
        elif self.delivery_id:
            raise ValidationError('Morning observations must not be linked to a delivery.')
        if self.density_15c is not None and not self.correction_source.strip():
            raise ValidationError('Record the approved table/instrument/reference used for density at 15°C.')


class SalaryShortageAdjustment(models.Model):
    deduction = models.ForeignKey(SalaryDeduction, on_delete=models.PROTECT, related_name='adjustments')
    request_id = models.UUIDField(unique=True)
    previous_amount = money()
    revised_amount = money()
    reason = models.CharField(max_length=500)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def salary_credit(self):
        return self.previous_amount - self.revised_amount

    class Meta:
        ordering = ['pk']


class ShiftDiscount(models.Model):
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, related_name='discounts')
    salesperson = models.ForeignKey(Salesperson, on_delete=models.PROTECT)
    request_id = models.UUIDField(unique=True)
    amount = positive_money()
    reason = models.CharField(max_length=500)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    voided = models.BooleanField(default=False)


class BulkSaleAllocation(models.Model):
    reading = models.ForeignKey(Reading, on_delete=models.PROTECT, related_name='bulk_allocations')
    customer = models.CharField(max_length=100)
    vehicle_number = models.CharField(max_length=30, blank=True)
    quantity = models.DecimalField(max_digits=16,decimal_places=3,validators=[MinValueValidator(Decimal('0.001'))])
    request_id = models.UUIDField(unique=True)
    reference = models.CharField(max_length=100,unique=True)
    reason = models.CharField(max_length=500)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def gross_value(self):
        return (self.quantity*self.reading.unit_price).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)


class SalaryPayment(models.Model):
    salary = models.ForeignKey(SalaryRecord,on_delete=models.PROTECT,related_name='payments')
    account = models.ForeignKey(MoneyAccount,on_delete=models.PROTECT)
    date = models.DateField()
    amount = positive_money()
    number = models.CharField(max_length=100,unique=True)
    request_id = models.UUIDField(unique=True)
    external_reference = models.CharField(max_length=100,blank=True)
    notes = models.CharField(max_length=500)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0),name='positive_salary_payment')]


class SalaryAdvance(models.Model):
    salesperson = models.ForeignKey(Salesperson,on_delete=models.PROTECT)
    account = models.ForeignKey(MoneyAccount,on_delete=models.PROTECT)
    date = models.DateField()
    amount = positive_money()
    number = models.CharField(max_length=100,unique=True)
    request_id = models.UUIDField(unique=True)
    external_reference = models.CharField(max_length=100,blank=True)
    notes = models.CharField(max_length=500)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def cleared_amount(self):
        return sum((r.amount for r in self.recoveries.all() if not r.voided),Decimal('0.00'))

    @property
    def remaining_amount(self):
        return self.amount-self.cleared_amount if not self.voided else Decimal('0.00')

    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(amount__gt=0),name='positive_salary_advance')]


class AdvanceRecovery(models.Model):
    advance = models.ForeignKey(SalaryAdvance,on_delete=models.PROTECT,related_name='recoveries')
    salary = models.ForeignKey(SalaryRecord,on_delete=models.PROTECT,related_name='advance_recoveries')
    date = models.DateField()
    amount = positive_money()
    request_id = models.UUIDField(unique=True)
    reason = models.CharField(max_length=500)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(amount__gt=0),name='positive_advance_recovery')]


class ShortageRecovery(models.Model):
    handover = models.ForeignKey(Handover,on_delete=models.PROTECT,related_name='shortage_recoveries')
    salary = models.ForeignKey(SalaryRecord,on_delete=models.PROTECT,related_name='shortage_receipts',null=True,blank=True)
    account = models.ForeignKey(MoneyAccount,on_delete=models.PROTECT)
    date = models.DateField()
    amount = positive_money()
    number = models.CharField(max_length=100,unique=True)
    request_id = models.UUIDField(unique=True)
    external_reference = models.CharField(max_length=100,blank=True)
    notes = models.CharField(max_length=500)
    voided = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(amount__gt=0),name='positive_shortage_recovery')]
