from django.contrib.admin import site, ModelAdmin, TabularInline

from serveradmin.changes.models import Commit, Addition, Modification, Deletion


site.register(Commit, type('CommitAdmin', (ModelAdmin, ), {
    'inlines': [
        type('AdditionInline', (TabularInline, ), {'model': Addition}),
        type('ModificationInline', (TabularInline, ), {'model': Modification}),
        type('DeletionInline', (TabularInline, ), {'model': Deletion}),
    ]
}))
