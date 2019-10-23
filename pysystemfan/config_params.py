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
            -- InstanceOf(cls, missing) - variable is dict, cls instance get
                                          constructed from it. (as cls(self, parameters)).
                                          If the variable is not present, behavior depends
                                          the value of "missing"
                                          Exception -- raises exception,
                                          anything else -- uses this as an argument to the class
                                          constructor.

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
                value = default.load(self, params.get(name, []))
            elif isinstance(default, InstanceOf):
                if default.missing == Exception and name not in params:
                    value = None
                else:
                    value = default.load(self, params.get(name, default.missing))
            else:
                value = params.get(name, default)

            if value is None:
                raise RuntimeError("Value of parameter " + name + " must be set")

            setattr(self, name, value)
            used_names.add(name)

        unused_param_names = set(params) - used_names
        unused_param_names.difference_update(param for param in params if param[0] == "_")

        if len(unused_param_names):
            raise RuntimeError("Parameters " + ", ".join(sorted(unused_param_names)) + " were not used")

    def dump_params(self, include_defaults = False):
        ret = collections.OrderedDict()
        for name, default, desription in self._params_iter():
            value = getattr(self, name)

            if isinstance(default, ListOf) or isinstance(default, InstanceOf):
                default.dump(value, include_defaults)
            elif include_defaults or value != default:
                ret[name] = value

        return ret

class ListOf:
    def __init__(self, classes):
        self.classes = classes

    def load(self, parent, data):
        return [InstanceOf._load(parent, item, self.classes) for item in data]

    def dump(self, data, include_defaults):
        if not include_defaults and not len(data):
            return []
        return [InstanceOf.dump(item, include_defaults) for item in data]

class InstanceOf:
    def __init__(self, classes, missing = Exception):
        self.classes = classes
        self.missing = missing

    def load(self, parent, data):
        return self._load(parent, data, self.classes)

    @staticmethod
    def _load(parent, data, classes):
        if len(classes) == 1:
            cls = classes[0]
        else:
            try:
                cls_name = data.pop("class")
            except KeyError:
                raise RuntimeError("Value of parameter " + name + " must be set") from None

            cls = None
            for candidate in classes:
                if candidate.__name__ == cls_name:
                    cls = candidate
                    break
            if cls is None:
                raise RuntimeError("No matching class found. Possible values are: " +
                                   ", ".join(candidate.__name__ for candidate in classes)) from None

        return cls(parent, data)

    @staticmethod
    def dump(data, include_defaults):
        ret = data.dump_params()
        ret["class"] = ret.__class__.__name__
