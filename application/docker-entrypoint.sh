#!/bin/bash

# upgrade the schema
alembic upgrade head

# run the application
exec "$@"
