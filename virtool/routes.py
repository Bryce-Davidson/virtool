import logging
from logging import getLogger

import virtool.account.api
import virtool.administrators.api
import virtool.analyses.api
import virtool.caches.api
import virtool.dev.api
import virtool.downloads.api
import virtool.genbank.api
import virtool.groups.api
import virtool.history.api
import virtool.hmm.api
import virtool.http.root
import virtool.http.ws
import virtool.indexes.api
import virtool.jobs.api
import virtool.labels.api
import virtool.oidc.api
import virtool.otus.api
import virtool.references.api
import virtool.samples.api
import virtool.settings.api
import virtool.spaces.api
import virtool.subtractions.api
import virtool.tasks.api
import virtool.uploads.api
import virtool.users.api
import virtool.messages.api
import virtool.ml.api


logger = getLogger("startup")

ROUTES = (
    virtool.account.api.routes,
    virtool.administrators.api.routes,
    virtool.analyses.api.routes,
    virtool.caches.api.routes,
    virtool.downloads.api.routes,
    virtool.genbank.api.routes,
    virtool.groups.api.routes,
    virtool.history.api.routes,
    virtool.hmm.api.routes,
    virtool.indexes.api.routes,
    virtool.http.root.routes,
    virtool.jobs.api.routes,
    virtool.labels.api.routes,
    virtool.messages.api.routes,
    virtool.ml.api.routes,
    virtool.otus.api.routes,
    virtool.oidc.api.routes,
    virtool.references.api.routes,
    virtool.samples.api.routes,
    virtool.settings.api.routes,
    virtool.spaces.api.routes,
    virtool.subtractions.api.routes,
    virtool.tasks.api.routes,
    virtool.uploads.api.routes,
    virtool.users.api.routes,
)


def setup_routes(app, dev: bool = False):
    app.router.add_get("/ws", virtool.http.ws.root)

    if dev:
        logger.info("Enabling development API")
        app.router.add_routes(virtool.dev.api.routes)

    for routes in ROUTES:
        app.router.add_routes(routes)
