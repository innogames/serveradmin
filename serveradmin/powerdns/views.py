from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Domain
from .utils import get_domain_settings, get_domains_out_of_sync


def domains(request: HttpRequest) -> HttpResponse:
    """Domain overview page

    :param request:
    :return:
    """
    settings = get_domain_settings()
    if not settings:
        messages.warning(request, 'No domain mapping configured in settings!')
        return render(request, 'empty.html')

    paginator = Paginator(Domain.objects.all(), 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'settings': settings,
        'domains': page_obj,
        'out_of_sync': get_domains_out_of_sync(),
    }
    return render(request, 'powerdns/domains.html', context)
