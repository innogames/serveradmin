from django.dispatch import Signal


pre_commit_critical = Signal()
pre_commit = Signal()
post_commit = Signal()

