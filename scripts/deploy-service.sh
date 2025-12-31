#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=$1
SERVICE_NAME=$2
TASK_NAME=$3
IMAGE_NAME=$4
IMAGE_TAG=$5
REPO_NAME=$6

echo "🚀 Deploying service: $SERVICE_NAME to cluster $CLUSTER_NAME"

# Validate Docker image exists
echo "Checking if image $IMAGE_NAME exists in ECR..."
if aws ecr describe-images --repository-name "$REPO_NAME" --image-ids imageTag="$IMAGE_TAG" >/dev/null 2>&1; then
    echo "✅ Image tag exists. Proceeding with deployment..."
else
    echo "❌ ERROR: Docker image tag $IMAGE_TAG does not exist in ECR repository $REPO_NAME."
    exit 1
fi

# -------------------------------
# Deployment
# -------------------------------
# getting the latest task revision
TASK_DEFINITION=$(aws ecs describe-task-definition --task-definition "$TASK_NAME")
echo "========= Got Latest Task Definition ========="

# preparing new task revision with new image
IMAGE_NEW_TASK_DEFINITION=$(echo "$TASK_DEFINITION" | jq --arg IMAGE "$IMAGE_NAME" \
  '.taskDefinition | .containerDefinitions[0].image = $IMAGE 
   | del(.taskDefinitionArn) 
   | del(.revision) 
   | del(.status) 
   | del(.requiresAttributes) 
   | del(.compatibilities) 
   | del(.registeredAt) 
   | del(.registeredBy)')
echo "========= New task definition prepared ========="

# creating new task revision
NEW_REVISION=$(aws ecs register-task-definition --cli-input-json "$IMAGE_NEW_TASK_DEFINITION")
NEW_REVISION_DATA=$(echo "$NEW_REVISION" | jq '.taskDefinition.revision')
echo "========= Registered new task revision ========="

# updating service with new task revision
NEW_SERVICE=$(aws ecs update-service --cluster "$CLUSTER_NAME" --service "$SERVICE_NAME" --task-definition "$TASK_NAME" --force-new-deployment)
echo "========= Updated service for Deployment ========="

# Wait for stabilization
aws ecs wait services-stable --cluster "$CLUSTER_NAME" --services "$SERVICE_NAME" || echo "⚠️ Still stabilizing"

echo "🎯 Deployment completed for $SERVICE_NAME"
