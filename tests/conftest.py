# Register all root fixtures for pytest via direct import from the split modules
from tests.fixtures.server_fixtures import *
from tests.fixtures.process_utils import *
from tests.fixtures.log_fixtures import *
from tests.fixtures.cleanup import *
from tests.fixtures.test_lifecycle import *
