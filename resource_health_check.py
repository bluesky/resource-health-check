#!/usr/bin/env python
import argparse
import logging
import socket
import subprocess
from collections import deque

from bluesky.log import LogFormatter
from bluesky.callbacks.zmq import RemoteDispatcher
from event_model import (RunRouter, DocumentRouter, Filler,
                         UndefinedAssetSpecification)
from databroker.core import discover_handlers


logger = logging.getLogger('validator')

handler_registry = {}


def validate_resource(resource):
    """
    Instiate a handler for the resource. Log success or any errors.
    """
    if not handler_registry:
        # Run handler discovery. If we find any, discovery will not be run
        # again. Note that this mutates a global variable.
        handler_registry.update(discover_handlers())

    filler = Filler(handler_registry, inplace=False)
    try:
        filler.get_handler(resource)
    except UndefinedAssetSpecification:
        logger.error(f'No spec {resource["spec"]} found')
    except Exception:
        logger.exception(f'Cannot read the data for {resource}')
    else:
        logger.info(f'Successfully read {resource}')


class Validator(DocumentRouter):
    """
    Cache Resource documents. When RunStop is received, validate them.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._resources = deque()

    def resource(self, doc):
        self._resources.append(doc)

    def stop(self, doc):
        # TODO Implement retry with backoff, as Filler does.
        for res in self._resources:
            validate_resource(res)


def validator_factory(name, doc):
    "A factory for the RunRouter that just makes a Validator for each Run."
    validator = Validator()
    validator(name, doc)
    return [validator], []


class LinuxMailHandler(logging.Handler):
    """
    Send email using the `mail` binary in a subprocess.

    This is a hack-ish stop gap until we learn how to configure SMTPHandler"""
    def __init__(self, email, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.email = email

    def emit(self, record):
        msg = self.format(record)
        subprocess.run(
            f'echo "{msg}" | mail -s '
            f'"Error report from resource health check on '
            f'{socket.gethostname()}" '
            f'"{self.email}"', shell=True)


def main():
    parser = argparse.ArgumentParser(
        description='Listen for documents over 0MQ and validate Resources.')
    parser.add_argument(
        'proxy_address', type=str,
        help="bluesky-0MQ-proxy out address, given as in localhost:5578")
    parser.add_argument(
        '--emails', type=str, required=False,
        help="comma-separated list of email adddresses")
    args = parser.parse_args()

    log_handler = logging.StreamHandler()  # stderr
    log_handler.setFormatter(LogFormatter())
    logger.setLevel('INFO')
    logger.addHandler(log_handler)

    # TODO Figure out how to use SMTPHandler.
    # server_name = socket.getfqdn()
    # smtp_handler = SMTPHandler(
    #     f'{server_name}',
    #     f'Validator <{getpass.getuser()}@{server_name}>',
    #     'mrakitin@bnl.gov', f'Health check from {server_name}')
    # smtp_handler.setFormatter(LogFormatter())
    # smtp_handler.setLevel('WARNING')
    # logger.addHandler(smtp_handler)

    for email_address in args.emails.split(','):
        mail_handler = LinuxMailHandler(email=email_address.strip())
        mail_handler.setFormatter(LogFormatter())
        mail_handler.setLevel('WARNING')
        logger.addHandler(mail_handler)

    rr = RunRouter([validator_factory])
    rd = RemoteDispatcher(args.proxy_address)
    rd.subscribe(rr)

    logger.info(f'Listening to {args.proxy_address}')

    rd.start()  # runs forever


if __name__ == '__main__':
    main()
