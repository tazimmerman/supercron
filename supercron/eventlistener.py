from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
import os
import sys
import traceback
import xmlrpc.client

from supervisor import childutils

from .crontab import CronTab


CronAction = Enum('CronAction', 'START STOP BOUNCE')


@dataclass
class CronEvent:
    name: str
    tab: CronTab
    action: CronAction
    last: Optional[int] = None

    def is_ready(self):
        curr = self.tab.next(default_utc=True)

        if self.last is None:
            self.last = curr
            return False
        else:
            # We're at or past the start/stop time.
            if (self.last - curr) <= 0:
                self.last = None
                return True
            else:
                self.last = curr
                return False


class SuperCron:
    def __init__(self, events: Dict[str, List[CronEvent]]):
        self.events = events
        self.rpc = childutils.getRPCInterface(os.environ)
        self.stdin = sys.stdin
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def run_forever(self):
        while True:
            # Wait puts us in the READY state.
            headers, payload = childutils.listener.wait(self.stdin, self.stdout)

            if not headers['eventname'].startswith('TICK'):
                # Ignore non-tick events.
                childutils.listener.ok(self.stdout)
                continue

            info = self.rpc.supervisor.getAllProcessInfo()
            info = {i['name']: i['statename'] for i in info}

            for prog, events in self.events.items():
                state = info[prog]

                for evt in events:
                    if evt.is_ready():
                        time = childutils.get_asctime()

                        if evt.action == CronAction.BOUNCE:
                            self.stderr.write(f'*** Bouncing {prog} at {time}. ***\n')
                            self.stderr.flush()
                            self.bounce_process(prog, state)

                        if evt.action == CronAction.STOP:
                            self.stderr.write(f'*** Stopping {prog} at {time}. ***\n')
                            self.stderr.flush()
                            self.stop_process(prog, state)

                        if evt.action == CronAction.START:
                            self.stderr.write(f'*** Starting {prog} at {time}. ***\n')
                            self.stderr.flush()
                            self.start_process(prog, state)

            childutils.listener.ok(self.stdout)

    def start_process(self, prog: str, state: str):
        if state in ('EXITED', 'STOPPED'):
            try:
                self.rpc.supervisor.startProcess(prog)
            except xmlrpc.client.Fault as e:
                traceback.print_exc()

    def stop_process(self, prog: str, state: str):
        if state == 'RUNNING':
            try:
                self.rpc.supervisor.stopProcess(prog)
            except xmlrpc.client.Fault as e:
                traceback.print_exc()

    def bounce_process(self, prog: str, state: str):
        if state in ('EXITED', 'RUNNING', 'STOPPED'):
            try:
                self.rpc.supervisor.stopProcess(prog, True)  # wait=True
                self.rpc.supervisor.startProcess(prog)
            except xmlrpc.client.Fault as e:
                traceback.print_exc()
