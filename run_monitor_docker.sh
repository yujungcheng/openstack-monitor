#!/bin/bash

if [[ $# -eq 3 ]]; then
  name=${1}
  image=${2}
  envfile=${3}
  echo "Input arguments: ${name} ${image} ${envfile}"
  
  docker run -d --name ${name} \
    --env-file ${envfile} \
    ${image}
  
  sleep 1

  docker ps -f name=${name}
else
  echo "Arguments: <container name> <image name> <environment file>"
fi
