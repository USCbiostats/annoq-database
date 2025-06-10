#!/bin/bash
set -e

# Function to display usage information
usage() {
    echo "Usage: $0 --index_name <index_name> --mappings_file <mappings_file> --settings_file <settings_file> --input_dir <input_dir>  --python_path <python_path>"
    exit 1
}

# Function to check if a file exists
check_file_exists() {
    if [ ! -f "$1" ]; then
        echo "Error: File $1 does not exist."
        exit 1
    fi
}

# Function to validate arguments
validate_arguments() {
    if [ -z "$INDEX_NAME" ]; then
        echo "Error: --index_name argument is required."
        usage
    fi
    if [ -z "$MAPPINGS_FILE" ]; then
        echo "Error: --mappings_file argument is required."
        usage
    fi
    if [ -z "$SETTINGS_FILE" ]; then
        echo "Error: --settings_file argument is required."
        usage
    fi
    if [ -z "$INPUT_DIR" ]; then
        echo "Error: --input_dir argument is required."
        usage
    fi

    if [ -z "$PYTHON_PATH" ]; then
	PYTHON_PATH=python3
    fi


    check_file_exists "$MAPPINGS_FILE"
    check_file_exists "$SETTINGS_FILE"
}

# Parse named arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --index_name) INDEX_NAME="$2"; shift ;;
        --mappings_file) MAPPINGS_FILE="$2"; shift ;;
        --settings_file) SETTINGS_FILE="$2"; shift ;;
        --input_dir) INPUT_DIR="$2"; shift ;;
        --python_path) PYTHON_PATH="$2"; shift ;;
        *) echo "Unknown parameter: $1"; usage ;;
    esac
    shift
done

validate_arguments

# Run Python scripts
echo "Running reinit script with index_name: $INDEX_NAME, mappings_file: $MAPPINGS_FILE, settings_file: $SETTINGS_FILE"
sudo $PYTHON_PATH -m src.reinit --index_name "$INDEX_NAME" --mappings_file "$MAPPINGS_FILE" --settings_file "$SETTINGS_FILE"

echo "Running index_es_json script with input_dir: $INPUT_DIR"
sudo $PYTHON_PATH -m src.index_es_json "$INPUT_DIR"
