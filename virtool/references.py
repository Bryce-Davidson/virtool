import gzip
import json
from cerberus import Validator

RIGHTS = [
    "build",
    "modify",
    "modify_otu",
    "remove"
]


def get_isolate_schema(require_id):
    return {
        "id": {
            "type": "string",
            "required": require_id
        },
        "source_type": {
            "type": "string",
            "required": True
        },
        "source_name": {
            "type": "string",
            "required": True
        },
        "default": {
            "type": "boolean",
            "required": True
        },
        "sequences": {
            "type": list,
            "schema": {
                "type": dict,
                "schema": get_sequence_schema(require_id)
            }
        }
    }


def get_sequence_schema(require_id):
    return {
        "_id": {
            "type": "string",
            "required": require_id
        },
        "accession": {
            "type": "string",
            "required": True
        },
        "definition": {
            "type": "string",
            "required": require_id
        },
        "sequence": {
            "type": "string",
            "required": True
        }
    }


def get_import_schema(require_id=True, require_meta=True):
    return {
        "data_type": {
            "type": "string",
            "required": require_meta
        },
        "organism": {
            "type": "string",
            "required": require_meta
        },
        "data": {
            "type": "list",
            "schema": {
                "type": dict,
                "schema": get_otu_schema(require_id)
            }
        }
    }


def get_otu_schema(require_id):
    return {
        "_id": {
            "type": "string",
            "required": require_id
        },
        "abbreviation": {
            "type": "string"
        },
        "name": {
            "type": "string",
            "required": True
        },
        "isolates": {
            "type": "list",
            "required": True,
            "schema": get_isolate_schema(require_id)
        }
    }


def get_owner_user(user_id):
    return {
        "id": user_id,
        "build": True,
        "modify": True,
        "modify_otu": True,
        "remove": True
    }


def detect_duplicates(otus):
    fields = ["_id", "name", "abbreviation"]

    seen = {field: set() for field in fields + ["isolate_id", "sequence_id"]}
    duplicates = {field: set() for field in fields + ["isolate_id", "sequence_id"]}

    for joined in otus:
        for field in fields:
            value = joined[field]

            if field == "abbreviation" and value == "":
                continue

            if field == "name":
                value = value.lower()

            if value in seen[field]:
                duplicates[field].add(value)
            else:
                seen[field].add(value)

        for isolate in joined["isolates"]:
            if "isolate_id" in isolate:
                isolate["id"] = isolate.pop("isolate_id")

            isolate_id = isolate["id"]

            if isolate_id in seen:
                duplicates["isolate_id"].add(isolate_id)
            else:
                seen["isolate_id"].add(isolate_id)

            for sequence in isolate["sequences"]:
                sequence_id = sequence.get("id", sequence["_id"])

                if sequence_id in seen["sequence_id"]:
                    duplicates["sequence_id"].add(sequence_id)
                else:
                    seen["sequence_id"].add(sequence_id)

    if not any(duplicates.values()):
        duplicates = None
    else:
        duplicates = {key: list(duplicates[key]) for key in duplicates}

    return duplicates


def load_reference_file(path):
    """
    Load a list of merged otus documents from a file handle associated with a Virtool ``otus.json.gz`` file.

    :param path: the path to the otus.json.gz file
    :type path: str

    :return: the otus data to import
    :rtype: dict

    """
    with open(path, "rb") as handle:
        with gzip.open(handle, "rt") as gzip_file:
            return json.load(gzip_file)
