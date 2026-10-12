#!/bin/sh
# Worker container entrypoint.
set -eu
exec arq app.worker.settings.WorkerSettings
