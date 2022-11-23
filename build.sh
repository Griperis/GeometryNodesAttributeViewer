#!/bin/bash

VERSION="1.0.1"
BUILDS_FOLDER="builds"

rm -rf ${BUILDS_FOLDER}/attribute_viewer
mkdir -p ${BUILDS_FOLDER}/attribute_viewer/data

# copy addon source files, remove pycache
cp __init__.py ${BUILDS_FOLDER}/attribute_viewer
cp data/attribute_viewer_nodes.blend ${BUILDS_FOLDER}/attribute_viewer/data

# change version in bl_info to match one in this file
sed -i "s/\"version\": ([0-9], [0-9], [0-9])/\"version\": (`echo ${VERSION} | sed -e 's/\./, /g'`)/" ${BUILDS_FOLDER}/attribute_viewer/__init__.py


# remove old zip, zip everything
rm -f attribute_viewer*.zip
cd ${BUILDS_FOLDER}; zip -r ../attribute_viewer_${VERSION}.zip attribute_viewer/*
echo "Release zip saved at 'attribute_viewer_${VERSION}.zip'"