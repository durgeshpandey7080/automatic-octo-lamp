from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Supplier,FuelPurchase,SupplierPayment,SupplierCredit
from .operations import staff_only,validate_date,audit
from .numbering import document_number

@transaction.atomic
def save_purchase(data,user):
 staff_only(user);data=dict(data)
 supplier=Supplier.objects.select_for_update().get(pk=data['supplier'].pk)
 if not supplier.active:raise ValidationError('Choose an active supplier.')
 validate_date(data['date'])
 if data['date']>data['delivery'].date:raise ValidationError('Invoice date cannot be after its delivery date.')
 record=FuelPurchase(**data,number=document_number('PUR'),recorded_by=user)
 record.full_clean();record.save()
 audit(user,record,'CREATE_PURCHASE','Supplier invoice linked to existing received stock.',after={'total':str(record.total),'delivery':record.delivery_id})
 return record

@transaction.atomic
def save_supplier_entry(kind,data,user):
 staff_only(user);data=dict(data)
 purchase=FuelPurchase.objects.select_for_update().get(pk=data['purchase'].pk)
 if purchase.voided:raise ValidationError('This invoice is void.')
 validate_date(data['date'])
 if data['date']<purchase.date:raise ValidationError('Entry date cannot precede invoice date.')
 if data['amount']>purchase.outstanding:raise ValidationError('Amount exceeds outstanding balance of Rs '+str(purchase.outstanding)+'.')
 if kind=='payment':
  if data['method']!='CASH' and not data.get('external_reference','').strip():raise ValidationError('Enter the real bank/UPI/POS transaction reference.')
  record=SupplierPayment(**data,number=document_number('SP'),recorded_by=user)
 elif kind=='credit':record=SupplierCredit(**data,number=document_number('SC'),recorded_by=user)
 else:raise ValidationError('Unknown supplier entry.')
 record.full_clean();record.save();audit(user,record,'CREATE_SUPPLIER_'+kind.upper(),'Saved against '+purchase.number,after={'amount':str(record.amount)})
 return record

@transaction.atomic
def reverse_supplier_entry(kind,pk,user,reason):
 staff_only(user)
 if not reason.strip():raise ValidationError('Enter a correction reason.')
 models={'purchase':FuelPurchase,'payment':SupplierPayment,'credit':SupplierCredit}
 if kind not in models:raise ValidationError('Unknown supplier entry.')
 record=models[kind].objects.select_for_update().get(pk=pk)
 if record.voided:raise ValidationError('Already reversed.')
 if kind=='purchase' and (record.payments.filter(voided=False).exists() or record.credit_notes.filter(voided=False).exists()):
  raise ValidationError('Reverse linked payments and credits before voiding this invoice.')
 record.voided=True;record.save();audit(user,record,'REVERSE_SUPPLIER_'+kind.upper(),reason,before={'active':True},after={'active':False})
 return record
