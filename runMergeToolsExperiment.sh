#!/bin/bash

cd "$(dirname "$0")"

if [ -f .env.local ]; then
  export $(grep -v '^#' .env.local | xargs)
else
  echo "Error: .env.local file not found!"
  exit 1
fi

EXPERIMENT_NAME=${EXPERIMENT_NAME-$(date +"%Y_%m_%d_%H_%M")}
EXECUTION_FOLDER=${EXECUTION_FOLDER-$PWD/executions/$EXPERIMENT_NAME}
OUTPUT_FOLDER=$EXECUTION_FOLDER/output
MERGE_ANALYSIS_FOLDER=$EXECUTION_FOLDER/mergeAnalysisOutput

THREADS=${THREADS-1}

mkdir -p $OUTPUT_FOLDER
mkdir -p $MERGE_ANALYSIS_FOLDER
mkdir -p $EXECUTION_FOLDER/clonedRepositories

docker build -t replication_env:latest .

echo "========================================"
echo "Experiment Name: $EXPERIMENT_NAME"
echo "Results will be saved to: $EXECUTION_FOLDER"
echo "Threads per run: $THREADS"
echo "========================================"

DOCKER_ARGS="--rm \
  -e HOST_USER_ID=$(id -u) \
  -e HOST_GROUP_ID=$(id -g) \
  -v $PWD/input:/usr/src/miningframework/input \
  -v $PWD/vendor:/usr/src/miningframework/dependencies \
  -v $MERGE_ANALYSIS_FOLDER:/usr/src/miningframework/mergeAnalysisOutput \
  -v $EXECUTION_FOLDER/clonedRepositories:/usr/src/miningframework/clonedRepositories \
  -v $OUTPUT_FOLDER:/usr/src/miningframework/output \
  replication_env:latest"

# 5. Execução das 5 linguagens (sem atalhos)
echo "Starting Rust Mining..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModule -t $THREADS -k -e .rs -a "${GITHUB_ACCESS_KEY}" input/mergeTools/filtered_repos/rs.csv mergeAnalysisOutput/rust

echo "Starting Javascript Mining..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModule -t $THREADS -k -e .js -a "${GITHUB_ACCESS_KEY}" input/mergeTools/filtered_repos/js.csv mergeAnalysisOutput/js

echo "Starting Go Mining..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModule -t $THREADS -k -e .go -a "${GITHUB_ACCESS_KEY}" input/mergeTools/filtered_repos/go.csv mergeAnalysisOutput/go

echo "Starting Python Mining..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModule -t $THREADS -k -e .py -a "${GITHUB_ACCESS_KEY}" input/mergeTools/filtered_repos/py.csv mergeAnalysisOutput/python

echo "Starting Java Mining..."
docker run $DOCKER_ARGS miningframework -i injectors.GenericMergeModuleJava -t $THREADS -k -e .java -a "${GITHUB_ACCESS_KEY}" input/mergeTools/filtered_repos/java.csv mergeAnalysisOutput/java

echo "All experiments finished!"