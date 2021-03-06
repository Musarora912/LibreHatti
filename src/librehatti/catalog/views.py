from django.http import HttpResponse, HttpResponseRedirect

from django.shortcuts import render

from django.db.models import Sum

from librehatti.catalog.models import Category
from librehatti.catalog.models import Product
from librehatti.catalog.models import *
from librehatti.catalog.forms import AddCategory
from librehatti.catalog.forms import ItemSelectForm
from librehatti.catalog.forms import ChangeRequestForm
from librehatti.catalog.models import HeaderFooter
from librehatti.catalog.request_change import request_notify

from librehatti.prints.helper import num2eng

from librehatti.suspense.models import SuspenseOrder

from librehatti.voucher.models import VoucherId, CalculateDistribution
from librehatti.voucher.models import FinancialSession

from django.core.urlresolvers import reverse

from django.contrib.auth.decorators import login_required
from django.db.models import Q

import simplejson

from django import forms

@login_required
def index(request):
    """
    It lists all the products and the user can select any product
    and can add them to the cart.
    """
    """error = {}
    categorylist = Category.objects.all()

    if categorylist.count() == 0:
        nocategory = True
        return render(request, 'catalog.html', {'nocategory': nocategory})
    productlist = Product.objects.all();

    if productlist.count() == 0:
        noproduct = True
        return render(request, 'catalog.html', {'noproduct': noproduct})

    return render(request,'catalog.html', {'productlist': productlist,
               'categorylist': categorylist})

    pass"""
    request_status = request_notify()
    return render(request,'index.html',{'request':request_status})


"""
This view allows filtering of sub category according to parent
category of item.
"""
@login_required
def select_sub_category(request):
    parent_category = request.GET['cat_id']
    sub_categories = Category.objects.filter(parent=parent_category)
    sub_category_dict = {}
    for sub_category in sub_categories:
        sub_category_dict[sub_category.id] = sub_category.name
    return HttpResponse(simplejson.dumps(sub_category_dict))


'''
This function reverse looks up the urls for the AJAX Requests
'''
def jsreverse(request):
    string_to_reverse = request.GET['string'];
    return HttpResponse(reverse(string_to_reverse))


"""
This view allows filtering of item according to sub category of item.
"""
@login_required
def select_item(request):
    cat_id = request.GET['cat_id']
    products = Product.objects.filter(category = cat_id)
    product_dict = {}
    for product in products:
        product_dict[product.id] = product.name
    return HttpResponse(simplejson.dumps(product_dict))

"""
This view allows filtering labs according to selected work.
"""
@login_required
def select_type(request):
    type_id = request.GET['type_id']
    if type_id == '1':
        work = 'Lab Work'
    else:
        work = 'Field Work'
    categories = Category.objects.filter(Q(name__icontains=work))
    category_dict = {}
    for category in categories:
        category_dict[category.id] = category.name.split(':')[0]
    return HttpResponse(simplejson.dumps(category_dict))         


"""
This view calculate taxes on purchased order, bill data
and save those values in database.
"""
@login_required
def bill_cal(request):
    old_post = request.session.get('old_post')
    purchase_order_id = request.session.get('purchase_order_id')
    purchase_order = PurchaseOrder.objects.get(id=purchase_order_id)
    purchase_order_obj = PurchaseOrder.objects.values('total_discount','tds').\
    get(id=purchase_order_id)
    purchase_item = PurchasedItem.objects.\
    filter(purchase_order=purchase_order_id).aggregate(Sum('price'))
    total = purchase_item['price__sum']
    price_total = total - purchase_order_obj['total_discount']
    totalplusdelivery = price_total
    surcharge = Surcharge.objects.values('id','value','taxes_included')
    delivery_rate = Surcharge.objects.values('value').\
    filter(tax_name = 'Transportation')
    distance = SuspenseOrder.objects.filter\
    (purchase_order = purchase_order_id).aggregate(Sum('distance_estimated'))
    if distance['distance_estimated__sum']:
        delivery_charges = int(distance['distance_estimated__sum'])*\
            delivery_rate[0]['value']
        totalplusdelivery = price_total + delivery_charges

    else:
        delivery_charges = 0

    for value in surcharge:
        surcharge_id = value['id']
        surcharge_value = value['value']
        surcharge_tax = value['taxes_included']
        if surcharge_tax == 1:
            taxes = round((totalplusdelivery * surcharge_value)/100)
            surcharge_obj = Surcharge.objects.get(id=surcharge_id)
            taxes_applied = TaxesApplied(purchase_order = purchase_order,
            surcharge = surcharge_obj, tax = taxes)
            taxes_applied.save()
    taxes_applied_obj = TaxesApplied.objects.\
    filter(purchase_order=purchase_order_id).aggregate(Sum('tax'))
    tax_total = taxes_applied_obj['tax__sum']
    grand_total = price_total + tax_total + delivery_charges
    amount_received = grand_total - purchase_order_obj['tds']
    bill = Bill(purchase_order = purchase_order, total_cost = price_total,
    total_tax = tax_total, grand_total = grand_total,
    delivery_charges = delivery_charges, amount_received = amount_received,
    totalplusdelivery=totalplusdelivery)
    bill.save()
    request.session['old_post'] = old_post
    request.session['purchase_order_id'] = purchase_order_id
    return HttpResponseRedirect(reverse\
        ("librehatti.catalog.views.order_added_success"))


@login_required
def list_products(request):
    all_products = Product.objects.all()
    all_categories=Category.objects.all().order_by('name')
    products_dict = { }
    for one_category in all_categories:
        if one_category.is_leaf_node():
            one_category_dict = {}
            products_list = Product.objects.filter(category=one_category)
            attributes_dict = { }
            for one_product in products_list:
                attributes_list = Catalog.objects.filter(product = one_product)
                attributes_dict[one_product] = attributes_list
            one_category_dict[one_category.name] = attributes_dict
            products_dict[one_category.id] = one_category_dict
    return render(request,'list_products.html',{'nodes':all_categories, \
        'products_dict':products_dict})


@login_required
def previous_value(request):
    old_post = request.session.get('old_post')
    purchase_order_id = request.session.get('purchase_order_id')
    Bill.objects.filter(purchase_order=purchase_order_id).delete()
    if SuspenseOrder.objects.filter(purchase_order=purchase_order_id):
        SuspenseOrder.objects.filter(purchase_order=purchase_order_id).delete()
    else:
        pass
    TaxesApplied.objects.\
    filter(purchase_order=purchase_order_id).delete()
    voucher_no = VoucherId.objects.values('voucher_no', 'session').\
    filter(purchase_order=purchase_order_id)
    for value in voucher_no:
        CalculateDistribution.objects.\
        get(voucher_no=value['voucher_no'], session=value['session']).delete()
    VoucherId.objects.filter(purchase_order=purchase_order_id).delete()
    return HttpResponseRedirect(reverse\
        ("librehatti.voucher.views.voucher_generate"))

@login_required
def order_added_success(request):
    order_id = request.session.get('purchase_order_id')
    details = PurchaseOrder.objects.values('buyer__first_name',\
        'buyer__last_name','buyer__customer__address__street_address',\
        'buyer__customer__title','buyer__customer__address__city',\
        'mode_of_payment__method','cheque_dd_number',\
        'cheque_dd_date').filter(id=order_id)[0]
    suspense_flag = 0
    suspense = SuspenseOrder.objects.filter(purchase_order=order_id)
    if suspense:
        suspense_flag = 1
    request_status = request_notify()
    return render(request,'catalog/order_added_success.html',\
        {'details': details,'order_id':order_id,'request':request_status,\
        'suspense_flag':suspense_flag})


@login_required
def change_request(request):
    if request.method == 'POST':
        sessiondata = ChangeRequestForm(request.POST)
        purchase_order_of_session = sessiondata.data['purchase_order']
        session = sessiondata.data['session']
        object = VoucherId.objects.filter(session_id = session).\
        filter(purchase_order_of_session = purchase_order_of_session).values()
        if object:
            voucherid = VoucherId.objects.\
            filter(purchase_order_of_session=purchase_order_of_session,\
            session_id=session).values('purchase_order_id')
            for value in voucherid:
                purchase_order = value['purchase_order_id']
            bill = Bill.objects.values('grand_total').\
            get(purchase_order=purchase_order)
            surcharge = TaxesApplied.objects.values('surcharge__tax_name',\
                'id','tax').filter(purchase_order_id = purchase_order)
            details = VoucherId.objects.values\
            ('purchase_order__buyer__first_name',\
                'purchase_order__buyer__last_name',
                'purchase_order__buyer__customer__address__street_address',\
                'purchase_order__buyer__customer__title',
                'purchase_order__buyer__customer__address__city',\
                'purchase_order__mode_of_payment__method',
                'purchase_order__cheque_dd_number',\
                'purchase_order__cheque_dd_date').\
                filter(purchase_order_of_session=purchase_order_of_session)[0]
            session_data = FinancialSession.objects.values(\
                'session_start_date','session_end_date').get(id=session)
            messages = "Purchase Order" + " : " + purchase_order_of_session +\
            " and Session" + " : " + str(session_data['session_start_date']) +\
            ":" + str(session_data['session_end_date'])
            request_status = request_notify()    
            return render(request,'catalog/change_form.html',\
                {'details': details,'order_id':purchase_order_of_session,\
                'session':session,'surcharge':surcharge,'bill':bill,\
                'messages':messages, 'request':request_status})
        else:
                form = ChangeRequestForm()
                errors = "No such purchase order number in selected session" 
                request_status = request_notify()
                temp = {"form" : form , "errors" : errors,\
                'request':request_status}
                
                return render(request, 'catalog/change_request.html', temp) 
    else:
        form = ChangeRequestForm()
        request_status = request_notify()
        return render(request, 'catalog/change_request.html', \
            {'form':form,'request':request_status})


@login_required
def price_per_unit(request):
    item_id = request.GET['item_id']
    product = Product.objects.values('price_per_unit').get(id=item_id)
    if product['price_per_unit'] is not None:
        return HttpResponse(product['price_per_unit'])
    else:
        return HttpResponse('fail')