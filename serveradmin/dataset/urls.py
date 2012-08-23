from django.conf.urls import patterns, url

urlpatterns = patterns(
    'serveradmin.dataset.views',
    url(r'^servertypes$', 'servertypes', name='dataset_servertypes'),
    url(r'^servertype/([\w\._-]+)$', 'view_servertype',
            name='dataset_view_servertype'),
    url(r'^servertype/delete/([\w\._-]+)$', 'delete_servertype',
            name='dataset_delete_servertype'),
    url(r'^attributes$', 'attributes', name='dataset_attributes'),
    url(r'^attributes/delete/(\w+)$', 'delete_attribute',
            name='dataset_delete_attribute'),
    url(r'^attributes/add$', 'add_attribute', name='dataset_add_attribute'),
)
