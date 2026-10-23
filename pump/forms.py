from django import forms
from decimal import Decimal
from django.forms import formset_factory
from .models import Shift, Reading, Salesperson, ManagerProfile, Handover, Debtor, DebtorTransaction, Expense, LubeProduct, LubeSale
from django.utils import timezone

class ShiftForm(forms.ModelForm):
    petrol_price = forms.DecimalField(label='Petrol price (Rs/L)', max_digits=8,
        decimal_places=3, min_value=Decimal('0.001'), required=False,
        widget=forms.NumberInput(attrs={'step': '0.001', 'min': '0.001'}))
    diesel_price = forms.DecimalField(label='Diesel price (Rs/L)', max_digits=8,
        decimal_places=3, min_value=Decimal('0.001'), required=False,
        widget=forms.NumberInput(attrs={'step': '0.001', 'min': '0.001'}))
    class Meta:
        model = Shift
        fields = ['date', 'number']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}

class ReadingForm(forms.ModelForm):
    salesperson = forms.ModelChoiceField(queryset=Salesperson.objects.filter(active=True),
        empty_label='Select person', required=True)
    class Meta:
        model = Reading
        fields = ['salesperson', 'opening_litres', 'closing_litres']
        widgets = {name: forms.NumberInput(attrs={'step': '0.001', 'min': '0'}) for name in fields if name != 'salesperson'}

ReadingFormSet = formset_factory(ReadingForm, extra=0, min_num=8, max_num=8,
    validate_min=True, validate_max=True, absolute_max=8)


class HandoverShiftForm(forms.Form):
    shift = forms.ModelChoiceField(queryset=Shift.objects.filter(readings__isnull=False).distinct(),
        label='Completed shift', empty_label='Choose a recorded shift')


class HandoverForm(forms.ModelForm):
    submitted_to = forms.ModelChoiceField(queryset=ManagerProfile.objects.filter(active=True),
        label='Cash submitted to', empty_label='Choose the receiving manager')

    class Meta:
        model = Handover
        fields = ['submitted_to', 'cash_received', 'card', 'paytm_business', 'phonepe_business', 'credit_sales', 'expenses', 'notes']
        labels = {'cash_received': 'Cash submitted (₹)', 'card': 'Card collections (₹)',
            'paytm_business': 'Paytm for Business (₹)', 'phonepe_business': 'PhonePe Business (₹)',
            'credit_sales': 'Debtor / credit sales (₹)',
            'expenses': 'Expenses (₹)', 'notes': 'References and explanation'}
        widgets = {name: forms.NumberInput(attrs={'step': '0.01', 'min': '0'}) for name in
            ['cash_received', 'card', 'paytm_business', 'phonepe_business', 'credit_sales', 'expenses']}
        widgets['notes'] = forms.Textarea(attrs={'rows': 3, 'maxlength': 1000})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .operations import digital_totals
        if self.instance.shift_id and self.instance.salesperson_id:
            tracked=digital_totals(self.instance.shift,self.instance.salesperson)
            if tracked is not None:
                for name,amount in tracked.items():
                    self.fields[name].disabled=True
                    self.initial[name]=amount
                    self.fields[name].help_text='Total from saved digital transaction records.'
        for name in ['credit_sales', 'expenses']:
            self.fields[name].disabled = True
            self.fields[name].help_text = 'Total from linked records. Add records before saving this handover.'


class ManagerProfileForm(forms.ModelForm):
    class Meta:
        model = ManagerProfile
        fields = ['name', 'phone', 'notes', 'active']
        labels = {'name': 'Manager name', 'phone': 'Phone (optional)', 'notes': 'Profile notes (optional)'}
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}


class DebtorForm(forms.ModelForm):
    opening_balance = forms.DecimalField(max_digits=22, decimal_places=2, min_value=0,
        initial=Decimal('0.00'), required=False, label='Opening amount owed (₹)',
        widget=forms.NumberInput(attrs={'min': '0', 'step': '0.01'}))
    opening_date = forms.DateField(initial=timezone.localdate, required=False,
        widget=forms.DateInput(attrs={'type': 'date'}), label='Opening balance date')

    class Meta:
        model = Debtor
        fields = ['name', 'phone', 'address', 'active']
        labels = {'name': 'Customer / debtor name', 'phone': 'Phone (optional)', 'address': 'Address (optional)'}

    def clean(self):
        values = super().clean()
        if values.get('opening_balance') and not values.get('opening_date'):
            self.add_error('opening_date', 'Enter the date for the opening balance.')
        if values.get('opening_date') and values['opening_date'] > timezone.localdate():
            self.add_error('opening_date', 'Future opening balances are not allowed.')
        return values


class DebtorProfileForm(forms.ModelForm):
    class Meta:
        model = Debtor
        fields = ['name', 'phone', 'address', 'active']


class CreditSaleForm(forms.Form):
    debtor = forms.ModelChoiceField(queryset=Debtor.objects.filter(active=True), label='Debtor / customer')
    shift = forms.ModelChoiceField(queryset=Shift.objects.filter(readings__isnull=False).distinct(), label='Recorded shift')
    salesperson = forms.ModelChoiceField(queryset=Salesperson.objects.all())
    amount = forms.DecimalField(max_digits=22, decimal_places=2, min_value=Decimal('0.01'),
        label='Credit sale amount (₹)', widget=forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}))
    reference = forms.CharField(max_length=100, label='Unique credit-slip reference')
    notes = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={'rows': 3}))


class DebtorPaymentForm(forms.Form):
    date = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={'type': 'date'}))
    amount = forms.DecimalField(max_digits=22, decimal_places=2, min_value=Decimal('0.01'),
        label='Repayment amount (₹)', widget=forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}))
    payment_method = forms.ChoiceField(choices=DebtorTransaction.METHODS)
    received_by = forms.ModelChoiceField(queryset=ManagerProfile.objects.filter(active=True), label='Received by manager')
    reference = forms.CharField(max_length=100, label='Unique receipt / transaction reference')
    notes = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={'rows': 3}))


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['date', 'source', 'shift', 'salesperson', 'category', 'description', 'payee', 'voucher', 'amount']
        labels = {'source': 'Paid from', 'shift': 'Recorded shift (shift cash only)',
            'salesperson': 'Salesperson (shift cash only)', 'voucher': 'Unique voucher / bill reference',
            'payee': 'Paid to (optional)', 'amount': 'Expense amount (₹)'}
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}),
            'amount': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'})}


class LubeProductForm(forms.ModelForm):
    class Meta:
        model = LubeProduct
        fields = ['name', 'unit', 'selling_price', 'reorder_level', 'active']
        labels = {'name': 'Product name and pack size', 'unit': 'Sales unit', 'selling_price': 'Current selling price per unit (₹)'}
        widgets = {'selling_price': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.sales.exists():
            self.fields['unit'].disabled = True


class LubeSaleForm(forms.ModelForm):
    product = forms.ModelChoiceField(queryset=LubeProduct.objects.filter(active=True))
    salesperson = forms.ModelChoiceField(queryset=Salesperson.objects.filter(active=True))
    shift = forms.ModelChoiceField(queryset=Shift.objects.filter(readings__isnull=False).distinct())

    class Meta:
        model = LubeSale
        fields = ['shift', 'salesperson', 'product', 'quantity', 'unit_price', 'reference']
        labels = {'quantity': 'Quantity in the product\'s sales unit', 'unit_price': 'Selling price per unit (₹)',
            'reference': 'Unique sale / bill reference'}
        widgets = {'quantity': forms.NumberInput(attrs={'step': '0.001', 'min': '0.001'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'})}


class SalaryForm(forms.Form):
    salesperson = forms.ModelChoiceField(queryset=Salesperson.objects.all())
    month = forms.DateField(label='Salary month', input_formats=['%Y-%m'],
        widget=forms.DateInput(format='%Y-%m', attrs={'type': 'month'}))
    base_salary = forms.DecimalField(label='Fixed monthly salary (Rs)', max_digits=22,
        decimal_places=2, min_value=Decimal('0.01'))

    def clean_month(self):
        month = self.cleaned_data['month'].replace(day=1)
        if month > timezone.localdate().replace(day=1):
            raise forms.ValidationError('Choose this month or an earlier month.')
        return month


from .models import Tank, TankOpening, FuelDelivery, TankDip
class TankOpeningForm(forms.ModelForm):
    class Meta:
        model = TankOpening
        fields = ['tank','date','litres']
        widgets = {'date':forms.DateInput(attrs={'type':'date'})}
        labels = {'litres':'Opening stock (litres)', 'date':'Opening business date'}

class FuelDeliveryForm(forms.ModelForm):
    class Meta:
        model = FuelDelivery
        fields = ['tank','date','litres','invoice','supplier','notes']
        widgets = {'date':forms.DateInput(attrs={'type':'date'})}
        labels = {'litres':'Litres received', 'invoice':'Unique invoice / delivery reference'}

class TankDipForm(forms.ModelForm):
    class Meta:
        model = TankDip
        fields = ['tank','shift','physical_litres','notes']
        labels = {'physical_litres':'Physical dip stock (litres)'}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['shift'].queryset = Shift.objects.filter(number=2).order_by('-date')


def automatic_number_fields(form):
    for name in ['reference','voucher','number']:
        if name in form.fields:
            field=form.fields[name]
            field.required=False;field.disabled=True;field.initial=''
            field.help_text='Generated automatically when saved.'
            field.widget.attrs['placeholder']='Auto-generated on save'

CreditSaleForm.base_fields['vehicle_number']=forms.CharField(max_length=30,required=False,label='Vehicle number')
CreditSaleForm.base_fields['fuel_product']=forms.ChoiceField(choices=[('','Amount-only credit'),('PETROL','Petrol'),('DIESEL','Diesel')],required=False)
CreditSaleForm.base_fields['quantity']=forms.DecimalField(max_digits=16,decimal_places=3,min_value=Decimal('0.001'),required=False,label='Fuel quantity (litres)')
CreditSaleForm.base_fields['saved_rate']=forms.DecimalField(max_digits=12,decimal_places=3,min_value=Decimal('0.001'),required=False,label='Saved shift rate (Rs/L)')


# Keep old service callers/imports compatible while browser forms always use generated numbers.
def _with_automatic_numbers(cls):
    original=cls.__init__
    def init(self,*args,**kwargs):
        original(self,*args,**kwargs)
        automatic_number_fields(self)
    cls.__init__=init
for _form in [CreditSaleForm,DebtorPaymentForm,ExpenseForm,LubeSaleForm,FuelDeliveryForm]:
    _with_automatic_numbers(_form)
