from pathlib import Path
import pytest
import logging
import random
import os
import time

from src.command_runner import CommandRunner
from src.yaml_parser import ConfigLoader

logs = logging.getLogger()

@pytest.fixture(scope="function")
def vm_create(request):
    results = {}
    runner = CommandRunner()
    vm_config = request.config.rootpath / "config" / "vm-config-tlbflush-on.yaml"
    logs.info(vm_config)
    count = getattr(request, "param", 1)
    for i in range(count):
        vm_name = "bsod-auto-" + str(random.randint(1,15))
        context_variables = {"VM_NAME": vm_name}
        replaced_config = request.config.rootpath / "replaced_config" / Path(vm_name).with_suffix(".yaml") 
        ConfigLoader.load_and_save(vm_config, replaced_config, context_variables)
        create = runner.run(f"oc apply -f {replaced_config}", shell=True)
        if create.success:
           logs.info(f"VM created with name {vm_name}")
           time.sleep(10)
           results[vm_name] = runner.run(f"oc get vm/{vm_name}  -n windows-bsod -o custom-columns=\"STATUS:.status.printableStatus\" --no-headers", shell=True)
    yield results
