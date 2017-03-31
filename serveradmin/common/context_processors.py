from django.conf import settings


def base(request):
    return {'MENU_TEMPLATES': settings.MENU_TEMPLATES}
