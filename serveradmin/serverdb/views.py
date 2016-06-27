from operator import attrgetter

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import Http404
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.urlresolvers import reverse

from serveradmin.dataset.base import lookups
from serveradmin.dataset.create import create_server
from serveradmin.dataset.commit import CommitError
from serveradmin.serverdb.models import (
    Servertype,
    Attribute,
    ServerStringAttribute,
    ServertypeAttribute,
    ChangeCommit,
    ChangeAdd,
    ChangeUpdate,
    ChangeDelete,
    clear_lookups,
)
from serveradmin.serverdb.forms import (
    AddServertypeForm,
    AddAttributeForm,
    EditServertypeAttributeForm,
    AddServertypeAttributeForm,
)


@login_required
def servertypes(request):
    return TemplateResponse(request, 'serverdb/servertypes.html', {
        'servertypes': Servertype.objects.all()
    })


@login_required
def view_servertype(request, id):
    servertype = get_object_or_404(Servertype, pk=id)

    return TemplateResponse(request, 'serverdb/view_servertype.html', {
        'servertype': servertype,
    })


@login_required
@permission_required('serverdb.add_servertype')
def add_servertype(request):
    if request.method == 'POST':
        form = AddServertypeForm(request.POST)
        if form.is_valid():
            stype = form.save()
            clear_lookups()
            return redirect('serverdb_view_servertype', stype.pk)
    else:
        form = AddServertypeForm()

    return TemplateResponse(request, 'serverdb/add_servertype.html', {
        'add_form': form
    })


@login_required
@permission_required('serverdb.delete_servertype')
def delete_servertype(request, servertype_name):
    stype = get_object_or_404(Servertype, pk=servertype_name)
    if request.method == 'POST':
        if 'confirm' in request.POST:
            stype.delete()
            clear_lookups()
            messages.success(request, u'Servertype deleted.')
        else:
            msg = u'Please confirm the usage of weapons of mass destruction.'
            messages.error(request, msg)
            return redirect('serverdb_view_servertype', servertype_name)
    return redirect('serverdb_servertypes')


@login_required
@permission_required('serverdb.change_servertype')
def manage_servertype_attr(request, servertype_name, attribute_name=None):
    stype = get_object_or_404(Servertype, pk=servertype_name)
    if attribute_name:
        form_class = EditServertypeAttributeForm
        attribute = get_object_or_404(Attribute, pk=attribute_name)
        stype_attr = get_object_or_404(
            ServertypeAttribute,
            _attribute=attribute,
            _servertype=stype,
        )
    else:
        form_class = AddServertypeAttributeForm
        stype_attr = None
        attribute = None

    if request.method == 'POST':
        form = form_class(stype, request.POST, instance=stype_attr)
        if form.is_valid():
            if stype_attr:
                stype_attr = form.save(commit=False)
                msg = 'Edited attribute "{0}" of "{1}"'.format(
                    stype_attr.attribute, stype
                )
            else:
                stype_attr = form.save(commit=False)
                stype_attr.servertype = stype
                msg = 'Added attribute "{0}" to "{1}"'.format(
                    stype_attr.attribute, stype
                )

            # Set default_value to None if empty and not string
            if stype_attr.attribute.type != 'string':
                if not form.cleaned_data['default_value']:
                    stype_attr.default_value = None

            stype_attr.save()
            clear_lookups()
            messages.success(request, msg)
            return redirect('serverdb_view_servertype', stype.pk)
    else:
        if stype_attr:
            form = form_class(stype, instance=stype_attr)
        else:
            form = form_class(stype)

    return TemplateResponse(request, 'serverdb/manage_servertype_attr.html', {
        'servertype': stype,
        'form': form,
        'edit': stype_attr is not None,
        'attribute': attribute,
    })


@login_required
@permission_required('serverdb.change_servertype')
def delete_servertype_attr(request, servertype_name, attrib_name):
    stype_attr = get_object_or_404(
        ServertypeAttribute,
        _attribute_id=attrib_name,
        _servertype_id=servertype_name,
    )

    if request.method == 'POST' and 'confirm' in request.POST:
        ServerStringAttribute.objects.filter(
            server__servertype=stype_attr.servertype,
            attrib=stype_attr.attrib
        ).delete()
        stype_attr.delete()
        messages.success(request, 'Deleted attribute {0}'.format(attrib_name))
        return redirect('serverdb_view_servertype', servertype_name)

    return TemplateResponse(request, 'serverdb/delete_servertype_attr.html', {
        'stype_attr': stype_attr
    })


@login_required
@permission_required('serverdb.add_servertype')
def copy_servertype(request, servertype_name):
    stype = get_object_or_404(Servertype, pk=servertype_name)
    if request.method == 'POST' and 'name' in request.POST:
        stype.copy(request.POST['name'])
        messages.success(request, u'Copied servertype')
    return redirect('serverdb_servertypes')


@login_required
def attributes(request):
    return TemplateResponse(request, 'serverdb/attributes.html', {
        'attributes': sorted(lookups.attributes.values(),
                             key=attrgetter('pk'))
    })


@login_required
@permission_required('serverdb.delete_attribute')
def delete_attribute(request, attribute_id):
    attribute = get_object_or_404(Attribute, pk=attribute_id)
    if request.method == 'POST' and 'confirm' in request.POST:
        messages.success(request, 'Attribute "{0}" deleted.'.format(attribute))
        attribute.delete()
        clear_lookups()
        return redirect('serverdb_attributes')
    else:
        return TemplateResponse(request, 'serverdb/delete_attribute.html', {
            'attribute': attribute
        })


@login_required
@permission_required('serverdb.add_attribute')
def add_attribute(request):
    if request.method == 'POST':
        add_form = AddAttributeForm(request.POST)
        if add_form.is_valid():
            attribute = add_form.save()
            clear_lookups()
            messages.success(
                request, 'Attribute "{0}" added'.format(attribute)
            )
            return redirect('serverdb_attributes')
    else:
        add_form = AddAttributeForm()
    return TemplateResponse(request, 'serverdb/add_attribute.html', {
        'form': add_form
    })


@login_required
def changes(request):
    commits = ChangeCommit.objects.order_by('-change_on').prefetch_related()
    paginator = Paginator(commits, 30)
    try:
        page = paginator.page(request.GET.get('page', 1))
    except (PageNotAnInteger, EmptyPage):
        page = paginator.page(1)

    return TemplateResponse(request, 'serverdb/changes.html', {
        'commits': page
    })


@login_required
def history(request):
    hostname = request.GET.get('hostname')
    if not hostname:
        raise Http404

    try:
        commit_id = int(request.GET['commit'])
    except (KeyError, ValueError):
        commit_id = None

    adds = ChangeAdd.objects.filter(hostname=hostname).select_related()
    updates = ChangeUpdate.objects.filter(hostname=hostname).select_related()
    deletes = ChangeDelete.objects.filter(hostname=hostname).select_related()

    if commit_id:
        adds = adds.filter(commit__pk=commit_id)
        updates = updates.filter(commit__pk=commit_id)
        deletes = deletes.filter(commit__pk=commit_id)

    change_list = ([('add', obj) for obj in adds] +
                   [('update', obj) for obj in updates] +
                   [('delete', obj) for obj in deletes])
    change_list.sort(key=lambda entry: entry[1].commit.change_on, reverse=True)

    for change in change_list:
        commit = change[1].commit
        if commit.user:
            commit.commit_by = commit.user.get_full_name()
        elif commit.app:
            commit.commit_by = commit.app.name
        else:
            commit.commit_by = 'unknown'

    return TemplateResponse(request, 'serverdb/history.html', {
        'change_list': change_list,
        'commit_id': commit_id,
        'hostname': hostname,
        'is_ajax': request.is_ajax(),
        'base_template': 'empty.html' if request.is_ajax() else 'base.html',
        'link': request.get_full_path()
    })


@login_required
def restore_deleted(request, change_commit):
    deleted = get_object_or_404(ChangeDelete,
                                hostname=request.POST.get('hostname'),
                                commit__pk=change_commit)

    server_obj = deleted.attributes
    try:
        create_server(server_obj, skip_validation=True, fill_defaults=False,
                      fill_defaults_all=False)
    except CommitError as e:
        messages.error(request, unicode(e))
    else:
        messages.success(request, 'Server restored.')
    return redirect(
        reverse('serverdb_history') + '?hostname=' + server_obj['hostname']
    )
