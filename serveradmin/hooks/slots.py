class HookError(Exception):
    pass


class HookSlot(object):
    def __init__(self, name, **params):
        for param, param_type in params.iteritems():
            if not isinstance(param_type, type):
                raise ValueError(
                    'Parameter {} of hook {} is not a valid type: {}'
                    .format(param, name, param_type)
                )

        self.name = name
        self._params = params
        self._hooks = []

    def validate(self, **kwargs):
        for param, param_type in self._params.iteritems():
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

        results = {}
        failures = []
        for hookfn in self._hooks:
            try:
                hookfn(**kwargs)
            except ValueError as e:
                failures.append('{}: {}'.format(hookfn.__name__, e.message))

        if failures:
            raise ValueError('\n'.join(failures))

        return results
