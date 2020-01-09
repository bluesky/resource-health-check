# Resource Health Check

This consumes a stream of bluesky documents and verifies that any external files
referenced can be opened. This is intended to notice corrupt files early.

It can be used from Python or from the commandline as a background service.

## Streaming Validation

### As a service consuming from 0MQ

This logs succcess and failure to the stderr. If emails are provided (optional)
each failure will cause an email to be sent.

```sh
./resource-health-check.py localhost:5578 --emails alice@example.com,bob@example.com
```

### In-process with the bluesky RunEngine

Given a `bluesky.RunEngine` instance `RE`,

```py
# Set up a logger to display the results.
import logging
log_handler = logging.StreamHandler()  # stderr
logger.setLevel('INFO')
logger.addHandler(log_handler)

from resource_health_check import validator_factory
from event_model import RunRouter

rr = RunRouter([validator_factory])
RE.subscribe(rr)
```

## Post-facto Validation

### With a service

If you are running the consumer service, feed it like so:

```py
# Set up a logger to display the results.
import logging
log_handler = logging.StreamHandler()  # stderr
logger.setLevel('INFO')
logger.addHandler(log_handler)

from bluesky.callbacks.zmq import Publisher

publisher = Publisher('localhost:5577')

# databroker v1 API
for name, doc in header.documents(fill=False):
    publisher(name, doc)

# databroker v2 API
for name, doc in run.canonical(fill='no'):
    publisher(name, doc)
```

### In one process

```py
# Set up a logger to display the results.
import logging
log_handler = logging.StreamHandler()  # stderr
logger.setLevel('INFO')
logger.addHandler(log_handler)

from resource_health_check import Validator

validator = Validator()

# databroker v1 API
for name, doc in header.documents(fill=False):
    publisher(name, doc)

# databroker v2 API
for name, doc in run.canonical(fill='no'):
    publisher(name, doc)
```
