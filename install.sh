#!/bin/bash
set -eu
VY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec "$VY_ROOT/bin/vyntar" install "$@"
