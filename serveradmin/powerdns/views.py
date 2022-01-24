from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Domain
from .utils import get_settings, get_out_of_sync


def domains(request: HttpRequest) -> HttpResponse:
    """Domain overview page

    :param request:
    :return:
    """
    settings = get_settings('domain')
    if not settings:
        messages.warning(request, 'No domain mapping configured in settings!')
        return render(request, 'empty.html')

    paginator = Paginator(Domain.objects.all(), 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'settings': settings,
        'domains': page_obj,
        'num_out_of_sync': len(get_out_of_sync('domain')),
    }
    return render(request, 'powerdns/domains.html', context)
