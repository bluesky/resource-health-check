# Resource Health Check

This consumes a stream of bluesky documents and verifies that any external files
referenced can be opened. This is intended to notice corrupt files early.

It can be used from Python or from the commandline as a background service.

## As a service

This logs succcess and failure to the stderr. If emails are provided (optional)
each failure will cause an email to be sent.

```sh
./resource-health-check.py localhost:5568 --emails alice@example.com,bob@example.com
```

## From Python

Given a `bluesky.RunEngine` instance `RE`,

```py
from resource_health_check import validator_factory
from event_model import RunRouter

rr = RunRouter([validator_factory])
RE.subscribe(rr)
```
