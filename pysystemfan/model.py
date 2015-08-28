from . import config_params

class Model(config_params.Configurable):
    _params = [
        ("storage_path", None, "File where to save the model"),
        ("parameter_variance", 0.01, "1-sigma change per hour of parameters other"
                                     "than external temperature"),
        ("temperature_variance", 0.5, "1-sigma change per hour of parameters other"
                                      "than external temperature"),
        ("thermometer_variance", 0.5, "Variance of thermometer measurements."),
    ]

    def __init__(self, fan, **params):
        self.process_params(params)
