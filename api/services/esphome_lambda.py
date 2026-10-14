"""Valeur YAML !lambda (code C++ ESPHome) partagée par les générateurs."""

import yaml


class ESPLambda:
    def __init__(self, code: str):
        self.code = code


def esp_lambda_representer(dumper, data):
    style = '|' if '\n' in data.code or '"' in data.code else None
    return dumper.represent_scalar('!lambda', data.code, style=style)


yaml.add_representer(ESPLambda, esp_lambda_representer)
