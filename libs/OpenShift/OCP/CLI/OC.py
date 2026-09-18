'''
Thin shim around the `oc` CLI with common-option auto-discovery.
'''
import re
import logging
from typing import Optional

from libs.utils.CmdExec import CmdExec, CmdRes

logs = logging.getLogger(__name__)


class OCcli:
    '''
    Thin shim around the `oc` CLI.

    At init, discovers common options via `oc options` and stores
    user-provided defaults. On each call, common opts go before the
    subcommand, subcommand-specific opts go after -- all as argv[],
    never shell=True.
    '''

    def __init__(
        self,
        cmdExec: Optional[CmdExec] = None,
        **defaults,
    ) -> None:
        '''
        Initialize and discover common options from `oc options`.

        :param cmdExec:
            Optional CmdExec instance (default: new CmdExec()).
        :param defaults:
            Default values for common options, e.g.
            namespace='windows-bsod', kubeconfig='/path/to/kc'.
        '''
        self.cmdExec = cmdExec or CmdExec()
        self.cmnOpt = {}       # 'namespace' -> {'short': '-n', 'long': '--namespace'}
        self.shortMap = {}     # '-n' -> 'namespace' (reverse lookup)
        self.defaults = defaults
        self._DiscoverOptions()

    def _DiscoverOptions(self) -> None:
        '''
        Parse `oc options` output to populate self.cmnOpt.
        '''
        result = self.cmdExec.Run(['oc', 'options'])
        if not result.success:
            logs.warning(f'Failed to discover oc options: {result.stderr}')
            return

        for line in result.stdout.splitlines():
            m = re.match(r'\s+(?:(-\w),\s+)?--([\w-]+)=', line)
            if m:
                short, name = m.group(1), m.group(2)
                self.cmnOpt[name] = {
                    'short': short,
                    'long': f'--{name}',
                }
                if short:
                    self.shortMap[short] = name

    def _IsCommon(self, key: str) -> bool:
        '''Check if a key matches a discovered common option.'''
        if len(key) == 1:
            return f'-{key}' in self.shortMap
        return key.replace('_', '-') in self.cmnOpt

    def Run(self, subCmd: str, *args, **opts) -> CmdRes:
        '''
        Execute: oc [cmnOpts...] subCmd [args...] [subCmdOpts...]

        :param subCmd:
            The oc subcommand (e.g. 'get', 'apply', 'delete').
        :param args:
            Positional args after the subcommand.
        :param opts:
            Keyword opts:
            - single-char key -> short flag (e.g. o='json' -> -o json)
            - multi-char key -> long flag (e.g. no_headers=True -> --no-headers)
            - True -> flag only, no value; False -> omitted entirely
            - common option (per `oc options`) -> placed before subCmd
            - otherwise -> placed after subCmd
        :return:
            CmdRes from CmdExec.Run.
        '''
        cmnArgs = []
        subArgs = []

        merged = {**self.defaults, **opts}

        for key, val in merged.items():
            if val is False:
                continue

            flag = f'-{key}' if len(key) == 1 else f'--{key.replace("_", "-")}'
            token = [flag] if val is True else [flag, str(val)]

            if self._IsCommon(key):
                cmnArgs.extend(token)
            else:
                subArgs.extend(token)

        cmd = ['oc', *cmnArgs, subCmd, *args, *subArgs]
        return self.cmdExec.Run(cmd)
