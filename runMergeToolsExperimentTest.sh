#!/bin/bash

cd "$(dirname "$0")"

if [ -f .env.local ]; then
  export $(grep -v '^#' .env.local | xargs)
else
  echo "Error: .env.local file not found!"
  exit 1
fi

PREFIX=""
if [ -n "$CONTAINER_NAME_PREFIX" ]; then
  PREFIX="${CONTAINER_NAME_PREFIX}_"
fi

EXPERIMENT_NAME="test_$(date +"%Y_%m_%d_%H_%M")"
EXECUTION_FOLDER=$PWD/executions/$EXPERIMENT_NAME
OUTPUT_FOLDER=$EXECUTION_FOLDER/output
MERGE_ANALYSIS_FOLDER=$EXECUTION_FOLDER/mergeAnalysisOutput
IMAGE_NAME="${PREFIX}replication_env_test:latest"

mkdir -p $OUTPUT_FOLDER
mkdir -p $MERGE_ANALYSIS_FOLDER
mkdir -p $EXECUTION_FOLDER/clonedRepositories

ANALYSIS_REPO_FLAG=""
if [ -n "$GITHUB_REPOSITORY" ]; then
  ANALYSIS_REPO_FLAG="-ar $GITHUB_REPOSITORY"
fi

echo "========================================"
echo "Executando Teste Rápido: $EXPERIMENT_NAME"
echo "Analysis Repo: ${GITHUB_REPOSITORY:-None}"
echo "Docker image name: $IMAGE_NAME"
echo "========================================"

docker build --pull -t "$IMAGE_NAME" .

DOCKER_ARGS="--rm \
  -e HOST_USER_ID=$(id -u) \
  -e HOST_GROUP_ID=$(id -g) \
  -v $PWD/input:/usr/src/miningframework/input \
  -v $PWD/vendor:/usr/src/miningframework/dependencies \
  -v $MERGE_ANALYSIS_FOLDER:/usr/src/miningframework/mergeAnalysisOutput \
  -v $EXECUTION_FOLDER/clonedRepositories:/usr/src/miningframework/clonedRepositories \
  -v $OUTPUT_FOLDER:/usr/src/miningframework/output \
  $IMAGE_NAME"

echo "Starting Rust Mining Test..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModule -t $THREADS -k -m 1 -e .rs -a "${GITHUB_ACCESS_KEY}" -r 42 $ANALYSIS_REPO_FLAG input/test/test_rs.csv mergeAnalysisOutput/rust

echo "Starting Javascript Mining Test..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModule -t $THREADS -k -m 1 -e .js -a "${GITHUB_ACCESS_KEY}" -r 42 $ANALYSIS_REPO_FLAG input/test/test_js.csv mergeAnalysisOutput/js

echo "Starting Go Mining Test..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModule -t $THREADS -k -m 1 -e .go -a "${GITHUB_ACCESS_KEY}" -r 42 $ANALYSIS_REPO_FLAG input/test/test_go.csv mergeAnalysisOutput/go

echo "Starting Python Mining Test..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModule -t $THREADS -k -m 1 -e .py -a "${GITHUB_ACCESS_KEY}" -r 42 $ANALYSIS_REPO_FLAG input/test/test_py.csv mergeAnalysisOutput/python

echo "Starting Java Mining Test..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModuleJava -t $THREADS -k -m 1 -e .java -a "${GITHUB_ACCESS_KEY}" -r 42 $ANALYSIS_REPO_FLAG input/test/test_java.csv mergeAnalysisOutput/java

echo "All Test Experiments Finished Successfully! Results are in $EXECUTION_FOLDER"