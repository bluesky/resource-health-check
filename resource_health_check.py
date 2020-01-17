#!/usr/bin/env python
import argparse
import logging
import socket
import subprocess
from collections import deque
from logging.handlers import SMTPHandler, QueueHandler, QueueListener
import queue

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

    with Filler(handler_registry, inplace=False) as filler:
        try:
            filler.get_handler(resource)
        except UndefinedAssetSpecification:
            logger.error(f'No spec {resource["spec"]} found')
            raise
        except Exception:
            logger.exception(f'Cannot read the data for {resource}')
            raise
        else:
            logger.info(f'Successfully read {resource}')


class Validator(DocumentRouter):
    """
    Cache Resource documents. When RunStop is received, validate them.
    """
    def __init__(self, *args, raise_errors=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._resources = deque()
        self.raise_errors = raise_errors

    def resource(self, doc):
        self._resources.append(doc)

    def stop(self, doc):
        # TODO Implement retry with backoff, as Filler does.
        for res in self._resources:
            try:
                validate_resource(res)
            except Exception:
                if self.raise_errors:
                    raise


def validator_factory(name, doc):
    "A factory for the RunRouter that just makes a Validator for each Run."
    validator = Validator()
    validator(name, doc)
    return [validator], []


def validator_factory_raising(name, doc):
    """A factory for the RunRouter that just makes a Validator for each Run.

       This factory will be raising errors in case of a broken resource.
    """
    validator = Validator(raise_errors=True)
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
            f'"{self.email}" &', shell=True)


def main():
    parser = argparse.ArgumentParser(
        description='Listen for documents over 0MQ and validate Resources.')
    parser.add_argument(
        'proxy_address', type=str,
        help="bluesky-0MQ-proxy out address, given as in localhost:5578")
    parser.add_argument(
        '--emails', required=False, nargs='*',
        help="space-separated list of email addresses")
    args = parser.parse_args()

    log_handler = logging.StreamHandler()  # stderr
    log_handler.setFormatter(LogFormatter())
    logger.setLevel('INFO')
    logger.addHandler(log_handler)

    if args.emails:
        server_name = socket.gethostname()
        smtp_handler = SMTPHandler(
            mailhost='localhost',
            fromaddr=f'Resource Health Check <noreply@{server_name}>',
            toaddrs=args.emails,
            subject=(f'Error report from resource health check on '
                     f'{server_name}')
        )
        smtp_handler.setFormatter(LogFormatter(color=False))
        smtp_handler.setLevel('WARNING')
        # Use QueueHandler in case sending email is slow. LogRecords flow
        # from QueueHandler -> Queue -> QueueListener -> SMTPHandler.
        cleanup_listener = True
        que = queue.Queue()
        queue_handler = QueueHandler(que)
        queue_listener = QueueListener(que, smtp_handler,
                                       respect_handler_level=True)
        logger.addHandler(queue_handler)
        queue_listener.start()
    else:
        cleanup_listener = False


    rr = RunRouter([validator_factory])
    rd = RemoteDispatcher(args.proxy_address)
    rd.subscribe(rr)

    logger.info(f'Listening to {args.proxy_address}')

    try:
        rd.start()  # runs forever
    finally:
        if cleanup_listener:
            queue_listener.stop()


if __name__ == '__main__':
    main()
