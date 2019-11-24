import argparse
import configparser

from collections import defaultdict
from typing import Dict, List, TextIO

from supercron.crontab import CronTab
from supercron.eventlistener import SuperCron, CronAction, CronEvent


def parse_file(fp: TextIO) -> Dict[str, List[CronEvent]]:
    parser = configparser.ConfigParser()

    try:
        parser.read_file(fp)
    finally:
        fp.close()

    events = defaultdict(list)

    for prog, sect in parser.items():
        if prog.startswith('program:'):
            _, prog = prog.split(':')
            start = sect.get('start_at')
            stop = sect.get('stop_at')
            bounce = sect.get('bounce_at')

            if (start and bounce) or (stop and bounce):
                raise ValueError("The 'bounce_at' setting may not be used "
                                 "with 'start_at' or 'stop_at'.")

            if start:
                tab = CronTab(start)
                action = CronAction.START
                event = CronEvent(prog, tab, action)
                events[prog].append(event)

            if stop:
                tab = CronTab(stop)
                action = CronAction.STOP
                event = CronEvent(prog, tab, action)
                events[prog].append(event)

            if bounce:
                tab = CronTab(bounce)
                action = CronAction.BOUNCE
                event = CronEvent(prog, tab, action)
                events[prog].append(event)

    return events


parser = argparse.ArgumentParser(__package__)
parser.add_argument('--file', type=argparse.FileType())
args = parser.parse_args()
events = parse_file(args.file)
cron = SuperCron(events)
cron.run_forever()
