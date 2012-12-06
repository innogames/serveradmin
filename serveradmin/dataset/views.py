import re
from operator import attrgetter, itemgetter

from django.http import Http404
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.cache import cache
from django import forms

from serveradmin.dataset.base import lookups
from serveradmin.dataset.models import (ServerType, Attribute, AttributeValue,
        ServerTypeAttributes)

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
    stype_attributes.sort(key=itemgetter('name'))

    return TemplateResponse(request, 'dataset/view_servertype.html', {
        'servertype': servertype,
        'attributes': stype_attributes
    })

@login_required
@permission_required('dataset.add_servertype')
def add_servertype(request):
    class AddForm(forms.ModelForm):
        class Meta:
            model = ServerType
            fields = ('name', )

    if request.method == 'POST':
        form = AddForm(request.POST)
        if form.is_valid():
            stype = form.save()
            _clear_lookups()
            return redirect('dataset_view_servertype', stype.name)
    else:
        form = AddForm()

    return TemplateResponse(request, 'dataset/add_servertype.html', {
        'add_form': form
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
@permission_required('dataset.change_servertype')
def manage_servertype_attr(request, servertype_name, attrib_name=None):
    class EditForm(forms.ModelForm):
        attrib_default = forms.CharField(label='Default', required=False)
        class Meta:
            model = ServerTypeAttributes
            fields = ('required', 'attrib_default', 'regex')
        
        def __init__(self, servertype, *args, **kwargs):
            self.servertype = servertype
            super(EditForm, self).__init__(*args, **kwargs)

        def clean_regex(self):
            regex = self.cleaned_data['regex']
            if regex is not None:
                try:
                    re.compile(regex)
                except re.error:
                    raise forms.ValidationError('Invalid regular expression')
            return regex

    class AddForm(EditForm):
        class Meta(EditForm.Meta):
            fields = ('attrib', ) + EditForm.Meta.fields

        def clean_attrib(self):
            attrib = self.cleaned_data['attrib']
            exists = ServerTypeAttributes.objects.filter(attrib=attrib,
                    servertype=self.servertype)
            if exists:
                error_msg = 'Attribute is already on this servertype'
                raise forms.ValidationError(error_msg)
            return attrib
    
    stype = get_object_or_404(ServerType, name=servertype_name)
    if attrib_name:
        form_class = EditForm
        attrib = get_object_or_404(Attribute, name=attrib_name)
        stype_attr = get_object_or_404(ServerTypeAttributes, attrib=attrib,
                servertype=stype)
    else:
        form_class = AddForm
        stype_attr = None
        attrib = None

    if request.method == 'POST':
        form = form_class(stype, request.POST, instance=stype_attr)
        if form.is_valid():
            if stype_attr:
                stype_attr = form.save(commit=False)
                msg = 'Edited attribute "{0}" of "{1}"'.format(
                        stype_attr.attrib.name, stype.name)
            else:
                stype_attr = form.save(commit=False)
                stype_attr.servertype = stype
                msg = 'Added attribute "{0}" to "{1}"'.format(
                        stype_attr.attrib.name, stype.name)
            
            # Set attrib_default to None if empty and not string
            if stype_attr.attrib.type != 'string':
                if not form.cleaned_data['attrib_default']:
                    stype_attr.attrib_default = None
            
            stype_attr.save()
            _clear_lookups()
            messages.success(request, msg)
            return redirect('dataset_view_servertype', stype.name)
    else:
        if stype_attr:
            form = form_class(stype, instance=stype_attr)
        else:
            form = form_class(stype)

    return TemplateResponse(request, 'dataset/manage_servertype_attr.html', {
        'servertype': stype,
        'form': form,
        'edit': stype_attr is not None,
        'attrib': attrib
    })

@login_required
@permission_required('dataset.change_servertype')
def delete_servertype_attr(request, servertype_name, attrib_name):
    stype_attr = get_object_or_404(ServerTypeAttributes,
                                   attrib__name=attrib_name,
                                   servertype__name=servertype_name)
    if request.method == 'POST' and 'confirm' in request.POST:
        AttributeValue.objects.filter(server__servertype=stype_attr.servertype,
                attrib=stype_attr.attrib).delete()
        stype_attr.delete()
        messages.success(request, 'Deleted attribute {0}'.format(attrib_name))
        return redirect('dataset_view_servertype', servertype_name)

    return TemplateResponse(request, 'dataset/delete_servertype_attr.html', {
        'stype_attr': stype_attr
    })

@login_required
@permission_required('dataset.add_servertype')
def copy_servertype(request, servertype_name):
    stype = get_object_or_404(ServerType, name=servertype_name)
    if request.method == 'POST' and 'name' in request.POST:
        stype.copy(request.POST['name'])
        messages.success(request, u'Copied servertype')
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
    if request.method == 'POST' and 'confirm' in request.POST:
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

