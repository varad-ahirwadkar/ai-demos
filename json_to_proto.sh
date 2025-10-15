#!/bin/bash

PYTHON_VERSION=3.12
CURR_DIR=$(pwd)

echo "Downloading default model_config.proto file"
curl https://raw.githubusercontent.com/triton-inference-server/common/refs/heads/main/protobuf/model_config.proto -o ${CURR_DIR}/model_config.proto

echo "Install protobuf dependency"
python${PYTHON_VERSION} -m pip install protobuf
pip${PYTHON_VERSION} install --prefer-binary --extra-index-url=https://wheels.developerfirst.ibm.com/ppc64le/linux libprotobuf==4.25.8
export PATH=${PATH}:/usr/local/lib/python${PYTHON_VERSION}/site-packages/libprotobuf/bin

echo "Generate python protobuf definition file.."
protoc --python_out=. model_config.proto

echo "Convert json model configuration file to protobuf format"
python${PYTHON_VERSION} json_to_proto.py
echo "Successfully generated config.pbtxt from json file.."

exit 0

