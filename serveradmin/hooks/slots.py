from logging import getLogger
from time import time

logger = getLogger('serveradmin')


class HookError(Exception):
    pass


class HookSlot(object):
    def __init__(self, name, **params):
        for param, param_type in params.items():
            if not isinstance(param_type, type):
                raise ValueError(
                    'Parameter {} of hook {} is not a valid type: {}'
                    .format(param, name, param_type)
                )

        self.name = name
        self._params = params
        self._hooks = []

    def validate(self, **kwargs):
        for param, param_type in self._params.items():
            if param not in kwargs:
                raise ValueError(
                    '{} hook: parameter {} is missing.'
                    .format(self.name, param)
                )
            if not isinstance(kwargs[param], param_type):
                raise ValueError(
                    '{} hook: parameter {} must be {}, got {}'
                    .format(self.name, param, param_type, type(kwargs[param]))
                )

        for arg in kwargs.keys():
            if arg not in self._params:
                raise ValueError(
                    '{} hook: unexpected argument {}'
                    .format(self.name, arg)
                )

    def connect(self, hookfn):
        """Attach a function to the hook slot"""
        assert hookfn not in self._hooks, 'Duplicate connection'
        self._hooks.append(hookfn)

    def connected(self, filterfn=None):
        """Decorator to attach a hook

        An additional filterfn can be specified, which will be called with
        the same parameters as the hook.  The actual hook function is
        called only if the filterfn returns True.
        """
        def decorator(fn):
            self.connect(fn, filterfn)
            return fn
        return decorator

    def __call__(self, *args, **kwargs):
        """Decorator to attach a hook"""
        def decorator(fn):
            self.connect(fn, *args, **kwargs)
            return fn
        return decorator

    def invoke(self, **kwargs):
        self.validate(**kwargs)
        start_time = time()
        for hookfn in self._hooks:
            hookfn(**kwargs)
            end_time = time()
            logger.info('hooks: Invoke: ' + (', '.join([
                'Function: {}'.format(hookfn.__name__),
                'Time elapsed: {:.3f}s'.format(end_time - start_time),
            ])))
            start_time = end_time
