import yaml
from string import Template
from pathlib import Path
from typing import Dict, Any
import logging

logs = logging.getLogger(__name__)

class ConfigLoader:
     '''Loads a YAML file, replaces placeholders, and saves the output to a new file'''

     @staticmethod
     def loadAndSave(sourcePath: Path, outputPath: Path, placeholders: Dict[str, Any]):
        '''
        Loads a YAML file, substitutes placeholders, and saves the result

        :param sourcePath:
        :param outputPath:
        :param placeholders:
        '''
        def _yamlSafeScalar(value: Any) -> str:
            '''Encodes a value as a properly quoted/escaped YAML scalar'''
            return yaml.safe_dump(value, default_flow_style=True).strip()

        if not sourcePath.exists():
           raise FileNotFoundError(f'Configuration file not found at: {sourcePath}')

        rawText = sourcePath.read_text(encoding='utf-8')
        template = Template(rawText)
        processedText = template.safe_substitute(placeholders)
        #safePlaceholders = {k: _yamlSafeScalar(v) for k, v in placeholders.items()}
        #processedText = template.safe_substitute(safePlaceholders)
        configDict = yaml.safe_load(processedText) or {}

        outputPath.parent.mkdir(parents=True, exist_ok=True)

        with open(outputPath, 'w', encoding='utf-8') as f:
            yaml.safe_dump(configDict, f, default_flow_style=False, sort_keys=False)
