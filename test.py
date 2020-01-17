import pytest
from ophyd.sim import NumpySeqHandler, img

from bluesky import RunEngine
from bluesky.plans import count
from event_model import RunRouter, UndefinedAssetSpecification
from resource_health_check import handler_registry, validator_factory_raising


def test():
    "A simple test demonstrating validation failure and success"
    handler_registry.clear()
    RE = RunEngine()
    rr = RunRouter([validator_factory_raising])
    RE.subscribe(rr)
    # This should fail because there is no handler registered.
    with pytest.raises(UndefinedAssetSpecification):
        RE(count([img]))
    # Register the handler...
    handler_registry.update({'NPY_SEQ': NumpySeqHandler})
    # ...and now the validator should be satisfied.
    RE(count([img]))
