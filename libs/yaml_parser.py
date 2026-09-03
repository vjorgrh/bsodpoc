import yaml
from string import Template
from pathlib import Path
from typing import Dict, Any
import logging

logs = logging.getLogger(__name__)

class ConfigLoader:
     """Loads a YAML file, replaces placeholders, and saves the output to a new file"""
   
     @staticmethod
     def load_and_save(source_path: Path, output_path: Path, placeholders: Dict[str, Any]):
        """
        Loads a YAML file, substitutes placeholders, and saves the result

        :param source_path:
        :param output_path:
        :param placeholders:
        """
        def _yaml_safe_scalar(value: Any) -> str:
            """Encodes a value as a properly quoted/escaped YAML scalar"""
            return yaml.safe_dump(value, default_flow_style=True).strip()

        if not source_path.exists():
           raise FileNotFoundError(f"Configuration file not found at: {source_path}")

        raw_text = source_path.read_text(encoding="utf-8")
        template = Template(raw_text)
        processed_text = template.safe_substitute(placeholders)
        #safe_placeholders = {k: _yaml_safe_scalar(v) for k, v in placeholders.items()}
        #processed_text = template.safe_substitute(safe_placeholders)
        config_dict = yaml.safe_load(processed_text) or {}
  
        output_path.parent.mkdir(parents=True, exist_ok=True)
  
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)
