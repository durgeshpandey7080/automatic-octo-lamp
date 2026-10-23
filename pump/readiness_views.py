from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from .models import Tank, Nozzle, TankOpening, MoneyAccount, LubeProduct, Salesperson, ManagerProfile, StaffAccess, Shift


@login_required
def setup_readiness(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Only the owner can review station setup.')
    tanks = list(Tank.objects.all())
    nozzles = list(Nozzle.objects.select_related('tank').order_by('number'))
    checks = [
        {'name':'Tank configuration', 'state':'Needs physical verification',
         'detail':f'{len(tanks)} tanks configured. Capacities and nozzle mappings cannot be verified from software alone.', 'link':'admin:pump_tank_changelist'},
        {'name':'Eight nozzles', 'state':'Configured' if [n.number for n in nozzles]==list(range(1,9)) else 'Missing configuration',
         'detail':f'{len(nozzles)} nozzles configured. Verify that each is connected to the actual tank shown below.', 'link':'admin:pump_nozzle_changelist'},
        {'name':'Opening tank stock', 'state':'Recorded' if tanks and TankOpening.objects.count()==len(tanks) else 'Not complete',
         'detail':f'{TankOpening.objects.count()} tank openings recorded. Actual measured stock and a business date are required.', 'link':'tank_stock'},
        {'name':'Cash and bank openings', 'state':'Recorded; reconcile to actual balances' if MoneyAccount.objects.exists() else 'Not entered',
         'detail':f'{MoneyAccount.objects.count()} accounts have opening balances. Missing balances are unknown, not zero.', 'link':'money_book'},
        {'name':'Lube products and stock', 'state':'Review stock baselines' if LubeProduct.objects.exists() else 'Not configured',
         'detail':f'{LubeProduct.objects.count()} lube products. Enter real product names, rates, units and opening quantities.', 'link':'lubes'},
        {'name':'Salespeople and receiving manager', 'state':'Profiles exist' if Salesperson.objects.filter(active=True).exists() and ManagerProfile.objects.filter(active=True).exists() else 'Profiles incomplete',
         'detail':f'{Salesperson.objects.filter(active=True).count()} active salespeople; {ManagerProfile.objects.filter(active=True).count()} active receiving managers.', 'link':'managers'},
        {'name':'Staff login roles', 'state':'Review assigned roles' if StaffAccess.objects.exists() else 'Owner logins only / no explicit roles',
         'detail':f'{StaffAccess.objects.count()} explicit local station roles. A salesperson profile is separate from a login.', 'link':'staff_access'},
        {'name':'Recovery copies', 'state':'Check current backup status',
         'detail':'Primary and secondary encrypted copies are configured on this PC. Check the latest result and preserve a separate recovery key.', 'link':'backups'},
    ]
    return render(request,'pump/setup_readiness.html',{'page_name':'Station setup readiness','checks':checks,
        'tanks':tanks,'nozzles':nozzles,'demo_present':any('DEMO' in t.name.upper() for t in tanks),
        'shifts':Shift.objects.count()})
