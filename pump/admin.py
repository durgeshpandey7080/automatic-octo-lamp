from django.contrib import admin
from .models import Tank, Nozzle, Shift, Reading, Salesperson, DailyFuelPrice, ManagerProfile, Handover, Debtor, DebtorTransaction, Expense, LubeProduct, LubeSale
from django.conf import settings
admin.site.site_header = settings.STATION_NAME
admin.site.site_title = settings.STATION_NAME
admin.site.index_title = 'Station administration'
@admin.register(Tank)
class TankAdmin(admin.ModelAdmin):
    list_display = ['name', 'fuel', 'capacity_litres', 'low_stock_litres']
    def get_readonly_fields(self, request, obj=None):
        return ['fuel'] if obj and (Reading.objects.filter(nozzle__tank=obj).exists() or obj.nozzle_set.filter(dutyassignment__isnull=False).exists()) else []
@admin.register(Salesperson)
class SalespersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'active']
    list_filter = ['active']
    search_fields = ['name']
@admin.register(Nozzle)
class NozzleAdmin(admin.ModelAdmin):
    list_display = ['number', 'tank']
    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and (obj is None or (not obj.reading_set.exists() and not obj.dutyassignment_set.exists()))
    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and (obj is None or (not obj.reading_set.exists() and not obj.dutyassignment_set.exists()))

class LedgerAdmin(admin.ModelAdmin):
    # Read-only ledger: adding/deleting isolated records would break shift continuity.
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
@admin.register(Shift)
class ShiftAdmin(LedgerAdmin):
    list_display = ['date', 'number', 'created_at']
    list_filter = ['date', 'number']
@admin.register(Reading)
class ReadingAdmin(LedgerAdmin):
    list_display = ['shift', 'nozzle', 'salesperson', 'litres_sold', 'unit_price', 'expected_amount']
    exclude = ['opening_rupees', 'closing_rupees']
    list_filter = ['shift__date', 'nozzle']

@admin.register(DailyFuelPrice)
class DailyFuelPriceAdmin(LedgerAdmin):
    list_display = ['date', 'fuel', 'price_per_litre']
    list_filter = ['fuel', 'date']

@admin.register(ManagerProfile)
class ManagerProfileAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'active']
    list_filter = ['active']
    search_fields = ['name', 'phone']

@admin.register(Handover)
class HandoverAdmin(LedgerAdmin):
    list_display = ['shift', 'salesperson', 'submitted_to', 'expected_sales', 'expected_cash', 'cash_received', 'status', 'recorded_by']
    list_filter = ['shift__date', 'submitted_to', 'salesperson']

@admin.register(Debtor)
class DebtorAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'active', 'balance']
    search_fields = ['name', 'phone']

@admin.register(DebtorTransaction)
class DebtorTransactionAdmin(LedgerAdmin):
    # Delete individual entries through Django's confirmation and audit log.
    actions = None

    def has_delete_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        if obj is None:
            return True
        if obj.kind == 'SALE' and Handover.objects.filter(
                shift=obj.shift, salesperson=obj.salesperson).exists():
            return False
        # Removing a charge must not leave repayments above the remaining debt.
        return obj.debtor.balance - obj.signed_amount >= 0

    def delete_model(self, request, obj):
        from .operations import audit
        audit(request.user,obj,'ADMIN_DELETE_CREDIT','Individual deletion confirmed in admin',before={'amount':str(obj.amount),'reference':obj.reference,'kind':obj.kind})
        super().delete_model(request,obj)

    list_display = ['date', 'debtor', 'kind', 'amount', 'reference', 'received_by']
    list_filter = ['kind', 'payment_method', 'date']
    search_fields = ['reference', 'debtor__name']

@admin.register(Expense)
class ExpenseAdmin(LedgerAdmin):
    list_display = ['date', 'voucher', 'description', 'category', 'source', 'amount', 'salesperson']
    list_filter = ['category', 'source', 'date']
    search_fields = ['voucher', 'description']

@admin.register(LubeProduct)
class LubeProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'unit', 'selling_price', 'active']
    def get_readonly_fields(self, request, obj=None):
        return ['unit'] if obj and obj.sales.exists() else []

@admin.register(LubeSale)
class LubeSaleAdmin(LedgerAdmin):
    list_display = ['shift', 'salesperson', 'product', 'quantity', 'unit_price', 'amount', 'reference']
    list_filter = ['product', 'shift__date']


from .models import SalaryRecord, SalaryDeduction
@admin.register(SalaryRecord)
class SalaryRecordAdmin(LedgerAdmin):
    list_display = ['month', 'salesperson', 'base_salary', 'shortage_deduction', 'net_salary']

@admin.register(SalaryDeduction)
class SalaryDeductionAdmin(LedgerAdmin):
    list_display = ['salary', 'handover', 'amount']


from .models import TankOpening, FuelDelivery, TankDip
@admin.register(TankOpening)
class TankOpeningAdmin(LedgerAdmin):
    list_display=['tank','date','litres']
@admin.register(FuelDelivery)
class FuelDeliveryAdmin(LedgerAdmin):
    list_display=['tank','date','litres','invoice','supplier']
@admin.register(TankDip)
class TankDipAdmin(LedgerAdmin):
    list_display=['tank','shift','physical_litres','expected_litres','variance']


from .models import AuditEvent, Duty, DutyAssignment, FuelTest, OtherIncome, DigitalCollection, LubeMovement, CashMovement, BankReconciliation, SalesReceipt, NumberSeries
for ledger_model in [AuditEvent,Duty,DutyAssignment,FuelTest,OtherIncome,DigitalCollection,LubeMovement,CashMovement,BankReconciliation,SalesReceipt,NumberSeries]:
    admin.site.register(ledger_model,LedgerAdmin)


from .models import Supplier,FuelPurchase,SupplierPayment,SupplierCredit
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display=['name','phone','active','outstanding']
    search_fields=['name','phone']
for model in [FuelPurchase,SupplierPayment,SupplierCredit]:admin.site.register(model,LedgerAdmin)

from .models import StaffAccess,BusinessDayClose
admin.site.register(StaffAccess,LedgerAdmin)
admin.site.register(BusinessDayClose,LedgerAdmin)

from .models import MoneyAccount,MoneyTransfer,BankAllocation
for model in [MoneyAccount,MoneyTransfer,BankAllocation]:admin.site.register(model,LedgerAdmin)

from .models import PaymentImportBatch,PaymentEvidence
for model in [PaymentImportBatch,PaymentEvidence]:admin.site.register(model,LedgerAdmin)

from .models import TankQualityObservation
admin.site.register(TankQualityObservation,LedgerAdmin)


from .models import SalaryShortageAdjustment, ShiftDiscount
@admin.register(SalaryShortageAdjustment)
class SalaryShortageAdjustmentAdmin(LedgerAdmin):
    list_display = ['deduction','previous_amount','revised_amount','reason','recorded_by','created_at']

@admin.register(ShiftDiscount)
class ShiftDiscountAdmin(LedgerAdmin):
    list_display = ['shift','salesperson','amount','reason','voided','recorded_by']

from .models import BulkSaleAllocation
@admin.register(BulkSaleAllocation)
class BulkSaleAllocationAdmin(LedgerAdmin):
    list_display = ['reference','reading','customer','quantity','voided']

from .models import SalaryPayment
@admin.register(SalaryPayment)
class SalaryPaymentAdmin(LedgerAdmin):
    list_display=['number','salary','date','account','amount','voided']

from .models import SalaryAdvance,AdvanceRecovery
@admin.register(SalaryAdvance)
class SalaryAdvanceAdmin(LedgerAdmin):
    list_display=['number','salesperson','date','account','amount','voided']
@admin.register(AdvanceRecovery)
class AdvanceRecoveryAdmin(LedgerAdmin):
    list_display=['advance','salary','date','amount','voided']

from .models import ShortageRecovery
admin.site.register(ShortageRecovery,LedgerAdmin)
