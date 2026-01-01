import os
import logging
import argparse
from .config import config


def _suppress_closed_resource_error(record):
    msg = record.getMessage()
    if "ClosedResourceError" in msg:
        return False
    exc = getattr(record, "exc_info", None)
    if exc and exc[0] and "ClosedResourceError" in str(exc[0]):
        return False
    return True


def setup_logging():
    if config.audit_log:
        logfile = config.audit_log
    else:
        logfile = os.path.expanduser(f'~/.mcp-grok/{config.log_timestamp}_{config.port}_audit.log')
    logdir = os.path.dirname(logfile)
    try:
        os.makedirs(logdir, exist_ok=True)
        with open(logfile, "a"):
            pass
    except Exception:
        logfile = "/tmp/server_audit.log"
        logdir = "/tmp"
        os.makedirs(logdir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.FileHandler(logfile), logging.StreamHandler()]
    )
    for name, log in logging.root.manager.loggerDict.items():
        if isinstance(log, logging.Logger):
            log.addFilter(_suppress_closed_resource_error)
    logging.getLogger().addFilter(_suppress_closed_resource_error)


def get_config_from_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port',
        type=int,
        default=config.port,
        help='Port to run MCP server on'
    )
    parser.add_argument(
        '--projects-dir',
        type=str,
        default=config.projects_dir,
        help='Base directory for MCP projects'
    )
    parser.add_argument(
        '--default-project',
        type=str,
        default=config.default_project,
        help='Default project to activate on server start'
    )
    parser.add_argument(
        '--audit-log',
        type=str,
        default=None,
        help='Path to audit log file'
    )
    args = parser.parse_args()
    config.port = args.port
    config.projects_dir = args.projects_dir
    config.default_project = args.default_project
    if args.audit_log:
        config.audit_log = args.audit_log
    return config


def main():
    # Defer importing the server class to avoid circular imports during package import
    from .server import MCPGrokServer

    get_config_from_cli()
    setup_logging()

    server = MCPGrokServer(config)
    server.startup()
    server.run()


if __name__ == "__main__":
    main()
