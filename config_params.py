class Configurable:
    """Classes inheriting from Configurable must define a class variable _params,
    which contains a list of (name, default_value, description) tuples of
    configuration variables.

    These can then be loaded from dict as instance variables using the process_params
    method, or stored back into dict using dump_params.

    name -- must be a valid python variable name
    default -- value
            -- None -- variable is required
            -- ListOf(cls) - variable is a required list of dicts, cls instances
                             get constructed from them. (as cls(self, **parameters))
    """

    def _params_iter(self):
        used_names = set()

        for klass in self.mro():
            try:
                params = klass._params
            except AttributeError:
                continue

            for name, default, description:
                if name in used_names:
                    continue
                used_names.add(name)
                yield (name, default, description)

    def process_params(self, **params):
        for name, default, description in self._params_iter():
            if isinstance(default, ListOf):
                value = [default._cls(self, item) for item in params.get(name)]
            else:
                value = params.get(name, default)
                if value is None:
                    raise RuntimeError("Value of parameter " + name + " must be set")

            setattr(self, name, value)

    def dump_params(self, include_defaults = True):
        ret = collections.OrderedDict()
        for name, default, desription in self._params_iter():
            value = getattr(self, name)

            if isinstance(default, ListOf):
                ret[name] = [item.dump_params(include_defaults) for item in value]
            elif include_defaults or value != default:
                ret[name] = value

        return ret

class ListOf:
    def __init__(self, cls):
        self._cls = cls
