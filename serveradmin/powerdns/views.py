from django.views.generic import ListView

from serveradmin.powerdns.models import Domain, Record


class DomainList(ListView):
    model = Domain
    template_name = 'powerdns/domain_list.html'
    paginate_by = 25
    ordering = 'name'


class RecordList(ListView):
    model = Record
    template_name = 'powerdns/record_list.html'
    paginate_by = 25
    ordering = 'domain_id'
