from operator import attrgetter
from django.http import Http404
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.cache import cache
from django import forms

from serveradmin.dataset.base import lookups
from serveradmin.dataset.models import ServerType, Attribute

@login_required
def servertypes(request):
    return TemplateResponse(request, 'dataset/servertypes.html', {
        'servertypes': ServerType.objects.order_by('name')
    })

@login_required
def view_servertype(request, servertype_name):
    try:
        servertype = lookups.stype_names[servertype_name]
    except KeyError:
        raise Http404

    stype_attributes = []
    for attr in servertype.attributes:
        stype_attr = lookups.stype_attrs[(servertype.name, attr.name)]
        attr_obj = lookups.attr_ids[stype_attr.attribute_id]
        stype_attributes.append({
            'name': attr_obj.name,
            'type': attr_obj.type,
            'multi': attr_obj.multi,
            'required': stype_attr.required,
            'regexp': stype_attr.regexp.pattern if stype_attr.regexp else None,
            'default': stype_attr.default
        })

    return TemplateResponse(request, 'dataset/view_servertype.html', {
        'servertype': servertype,
        'attributes': stype_attributes
    })

@login_required
@permission_required('dataset.delete_servertype')
def delete_servertype(request, servertype_name):
    stype = get_object_or_404(ServerType, name=servertype_name)
    if request.method == 'POST':
        if 'confirm' in request.POST:
            stype.delete()
            _clear_lookups()
            messages.success(request, u'Servertype deleted.')
        else:
            msg = u'Please confirm the usage of weapons of mass destruction.'
            messages.error(request, msg)
            return redirect('dataset_view_servertype', servertype_name)
    return redirect('dataset_servertypes')

@login_required
def attributes(request):
    return TemplateResponse(request, 'dataset/attributes.html', {
        'attributes': sorted(lookups.attr_names.values(),
                             key=attrgetter('name'))
    })

@login_required
@permission_required('dataset.delete_attribute')
def delete_attribute(request, attribute_name):
    attribute = get_object_or_404(Attribute, name=attribute_name)
    if request.method == 'POST':
        attribute.delete()
        _clear_lookups()
        messages.success(request, u'Attribute "{0}" deleted'.format(
                    attribute.name))
        return redirect('dataset_attributes')
    else:
        return TemplateResponse(request, 'dataset/delete_attribute.html', {
            'attribute': attribute
        })

@login_required
@permission_required('dataset.add_attribute')
def add_attribute(request):
    class AddForm(forms.ModelForm):
        class Meta:
            model = Attribute
            fields = ('name', 'type', 'multi')

    if request.method == 'POST':
        add_form = AddForm(request.POST)
        if add_form.is_valid():
            attribute = add_form.save()
            _clear_lookups()
            messages.success(request, u'Attribute "{0}" added'.format(
                    attribute.name))
            return redirect('dataset_attributes')
    else:
        add_form = AddForm()
    return TemplateResponse(request, 'dataset/add_attribute.html', {
        'form': add_form
    })

def _clear_lookups():
    cache.delete('dataset_lookups_version')

