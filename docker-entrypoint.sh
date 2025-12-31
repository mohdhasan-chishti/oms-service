#!/bin/bash
set -e

# Write .env from Secrets Manager
echo "$ENV_FILE_CONTENT" > /application/.env
export $(grep -v '^#' /application/.env | xargs)

# Write JSON secrets from Secrets Manager to files
echo "$ECS_TASK_DEFINITION_JSON" > /application/ecs-task-definition.json
echo "$FIREBASE_APP_JSON" > /application/firebase_app.json
echo "$FIREBASE_POS_JSON" > /application/firebase_pos.json

# Start the app
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
