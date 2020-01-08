from copy import deepcopy
from typing import Union

import dictdiffer

import virtool.otus.db
import virtool.errors
import virtool.history.utils
import virtool.otus.utils
import virtool.utils
from virtool.api import paginate

MOST_RECENT_PROJECTION = [
    "_id",
    "description",
    "method_name",
    "user",
    "otu",
    "created_at"
]

LIST_PROJECTION = [
    "_id",
    "description",
    "method_name",
    "created_at",
    "index",
    "otu",
    "reference",
    "user"
]

PROJECTION = LIST_PROJECTION + [
    "diff"
]


async def add(db, method_name, old, new, description, user_id, silent=False):
    """
    Add a change document to the history collection.

    :param db: the application database client
    :type db: :class:`~motor.motor_asyncio.AsyncIOMotorClient`

    :param method_name: the name of the handler method that executed the change
    :type method_name: str

    :param old: the otu document prior to the change
    :type new: Union[dict, None]

    :param new: the otu document after the change
    :type new: Union[dict, None]

    :param description: a human readable description of the change
    :type description: str

    :param user_id: the id of the requesting user
    :type user_id: str

    :param silent: don't dispatch a message
    :type: silent: bool

    :return: the change document
    :rtype: Coroutine[dict]

    """
    try:
        otu_id = old["_id"]
    except TypeError:
        otu_id = new["_id"]

    try:
        otu_name = old["name"]
    except TypeError:
        otu_name = new["name"]

    try:
        otu_version = int(new["version"])
    except (TypeError, KeyError):
        otu_version = "removed"

    try:
        ref_id = old["reference"]["id"]
    except (TypeError, KeyError):
        ref_id = new["reference"]["id"]

    document = {
        "_id": ".".join([str(otu_id), str(otu_version)]),
        "method_name": method_name,
        "description": description,
        "created_at": virtool.utils.timestamp(),
        "otu": {
            "id": otu_id,
            "name": otu_name,
            "version": otu_version
        },
        "reference": {
            "id": ref_id
        },
        "index": {
            "id": "unbuilt",
            "version": "unbuilt"
        },
        "user": {
            "id": user_id
        }
    }

    if method_name == "create":
        document["diff"] = new

    elif method_name == "remove":
        document["diff"] = old

    else:
        document["diff"] = virtool.history.utils.calculate_diff(old, new)

    await db.history.insert_one(document, silent=silent)

    return document


async def find(db, req_query, base_query=None):
    data = await paginate(
        db.history,
        {},
        req_query,
        base_query=base_query,
        sort="otu.version",
        projection=LIST_PROJECTION,
        reverse=True
    )

    return data


async def get(app, change_id):
    """
    Get a complete history document identified by the passed `changed_id`.

    Loads diff field from file if necessary. Returns `None` if the document does not exist.

    """
    document = await app["db"].history.find_one(change_id, PROJECTION)

    if document and document["diff"] == "file":
        otu_id, otu_version = change_id.split(".")

        document["diff"] = await virtool.history.utils.read_diff_file(
            app["settings"]["data_path"],
            otu_id,
            otu_version
        )

    return virtool.utils.base_processor(document)


async def get_contributors(db, query):
    """
    Return an list of contributors and their contribution count for a specific set of history.

    :param db: the application database client
    :type db: :class:`~motor.motor_asyncio.AsyncIOMotorClient`

    :param query: a query to filter scanned history by
    :type query: dict

    :return: a list of contributors to the scanned history changes
    :rtype: List[dict]

    """
    cursor = db.history.aggregate([
        {"$match": query},
        {"$group": {
            "_id": "$user.id",
            "count": {"$sum": 1}
        }}
    ])

    return [{"id": c["_id"], "count": c["count"]} async for c in cursor]


async def get_most_recent_change(db, otu_id):
    """
    Get the most recent change for the otu identified by the passed ``otu_id``.

    :param db: the application database client
    :type db: :class:`~motor.motor_asyncio.AsyncIOMotorClient`

    :param otu_id: the target otu_id
    :type otu_id: str

    :return: the most recent change document
    :rtype: Coroutine[dict]

    """
    return await db.history.find_one({
        "otu.id": otu_id,
        "index.id": "unbuilt"
    }, MOST_RECENT_PROJECTION, sort=[("otu.version", -1)])


async def patch_to_verified(db, otu_id):
    current = await virtool.otus.db.join(db, otu_id) or dict()

    if current and current["verified"]:
        return current

    patched = deepcopy(current)

    async for change in db.history.find({"otu.id": otu_id}, sort=[("otu.version", -1)]):
        if change["method_name"] == "remove":
            patched = change["diff"]

        elif change["method_name"] == "create":
            return None

        else:
            diff = dictdiffer.swap(change["diff"])
            patched = dictdiffer.patch(diff, patched)

        if patched["verified"]:
            return patched


async def patch_to_version(app, otu_id: str, version: Union[str, int]) -> tuple:
    """
    Take a joined otu back in time to the passed ``version``. Uses the diffs in the change documents associated with
    the otu.

    :param app: the application object
    :param otu_id: the id of the otu to patch
    :param version: the version to patch to
    :return: the current joined otu, patched otu, and the ids of changes reverted in the process

    """
    db = app["db"]

    # A list of history_ids reverted to produce the patched entry.
    reverted_history_ids = list()

    current = await virtool.otus.db.join(db, otu_id) or dict()

    if "version" in current and current["version"] == version:
        return current, deepcopy(current), reverted_history_ids

    patched = deepcopy(current)

    # Sort the changes by descending timestamp.
    async for change in db.history.find({"otu.id": otu_id}, sort=[("otu.version", -1)]):
        if change["otu"]["version"] == "removed" or change["otu"]["version"] > version:
            reverted_history_ids.append(change["_id"])

            if change["diff"] == "file":
                change["diff"] = await virtool.history.utils.read_diff_file(
                    app["settings"]["data_path"],
                    otu_id,
                    change["otu"]["version"]
                )

            if change["method_name"] == "remove":
                patched = change["diff"]

            elif change["method_name"] == "create":
                patched = None

            else:
                diff = dictdiffer.swap(change["diff"])
                patched = dictdiffer.patch(diff, patched)
        else:
            break

    if current == {}:
        current = None

    return current, patched, reverted_history_ids


async def revert(app, change_id: str):
    """
    Revert a history change given by the passed ``change_id``.

    :param app: the application object
    :param change_id: a unique id for the change
    :return: the updated OTU
    """
    db = app["db"]

    change = await db.history.find_one({"_id": change_id}, ["index"])

    if change["index"]["id"] != "unbuilt" or change["index"]["version"] != "unbuilt":
        raise virtool.errors.DatabaseError("Change is included in a build an not revertible")

    otu_id, otu_version = change_id.split(".")

    if otu_version != "removed":
        otu_version = int(otu_version)

    _, patched, history_to_delete = await patch_to_version(
        app,
        otu_id,
        otu_version - 1
    )

    # Remove the old sequences from the collection.
    await db.sequences.delete_many({"otu_id": otu_id})

    if patched is not None:
        patched_otu, sequences = virtool.otus.utils.split(patched)

        # Add the reverted sequences to the collection.
        for sequence in sequences:
            await db.sequences.insert_one(sequence)

        # Replace the existing otu with the patched one. If it doesn't exist, insert it.
        await db.otus.replace_one({"_id": otu_id}, patched_otu, upsert=True)

    else:
        await db.otus.delete_one({"_id": otu_id})

    await db.history.delete_many({"_id": {"$in": history_to_delete}})

    return patched
