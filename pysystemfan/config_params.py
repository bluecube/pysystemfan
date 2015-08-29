import collections

class Configurable:
    """Classes inheriting from Configurable must define a class variable _params,
    which contains a list of (name, default_value, description) tuples of
    configuration variables.

    These can then be loaded from dict as instance variables using the process_params
    method, or stored back into dict using dump_params.

    name -- must be a valid python variable name
    default -- value
            -- None -- variable is required
            -- ListOf(cls) - variable is a optional list of dicts, cls instances
                             get constructed from them. (as cls(self, parameters))
            -- InstanceOf(cls) - variable is a required dict, cls instance
                                 get constructed from it. (as cls(self, parameters))
    """

    def _params_iter(self):
        used_names = set()

        for klass in self.__class__.mro():
            try:
                params = klass._params
            except AttributeError:
                continue

            for name, default, description in params:
                if name in used_names:
                    continue
                used_names.add(name)
                yield (name, default, description)

    def process_params(self, params):
        used_names = set()

        for name, default, description in self._params_iter():
            if isinstance(default, ListOf):
                value = [default._cls(self, item) for item in params.get(name, [])]
            elif isinstance(default, InstanceOf):
                value = default._cls(self, params.get(name))
            else:
                value = params.get(name, default)
                if value is None:
                    raise RuntimeError("Value of parameter " + name + " must be set")

            setattr(self, name, value)
            used_names.add(name)

        unused_param_names = set(params) - used_names
        if len(unused_param_names):
            raise RuntimeError("Parameters " + ", ".join(sorted(unused_param_names)) + " were not used")

    def dump_params(self, include_defaults = False):
        ret = collections.OrderedDict()
        for name, default, desription in self._params_iter():
            value = getattr(self, name)

            if isinstance(default, ListOf):
                ret[name] = [item.dump_params(include_defaults) for item in value]
            elif isinstance(default, InstanceOf):
                ret[name] = value.dump_params(include_defaults)
            elif include_defaults or value != default:
                ret[name] = value

        return ret

class ListOf:
    def __init__(self, cls):
        self._cls = cls

class InstanceOf:
    def __init__(self, cls):
        self._cls = cls
