#!/usr/bin/env python
# coding=utf-8
"""Test base files
"""
import aiohttp
import asyncio
import json
import mock
import pytest
import taskcluster.exceptions


GOOD_GPG_KEYS = {
    "docker.root@example.com": {
        "fingerprint": "BFCEA6E98A1C2EC4918CBDEE9DA033D5FFFABCCF",
        "keyid": "FFFABCCF",
    },
    "docker@example.com": {
        "fingerprint": "F612354DFAF46BAADAE23801CD3C13EFBEAB7ED4",
        "keyid": "BEAB7ED4",
    },
    "scriptworker@example.com": {
        "fingerprint": "FB7765CD0FC616FF7AC961A1D9DC50F64C7D44CF",
        "keyid": "4C7D44CF",
    },
}

BAD_GPG_KEYS = {
    "unknown@example.com": {
        "fingerprint": "B45FE2F4035C3786120998174ACA2B25224905DA",
        "keyid": "224905DA",
    },
}

ARTIFACT_SHAS = {
    "public/foo": "b5bb9d8014a0f9b1d61e21e796d78dccdf1352f23cd32812f4850b878ae4944c",
    "public/baz": "bf07a7fbb825fc0aae7bf4a1177b2b31fcf8a3feeaf7092761e18c859ee52a9c",
    "public/logs/bar": "7d865e959b2466918c9863afca942d0fb89d7c9ac0c99bafc3749504ded97730",
}


def read(path):
    """Return the contents of a file.
    """
    with open(path, "r") as fh:
        return fh.read()


def touch(path):
    """ Create an empty file.  Different from the system 'touch' in that it
    will overwrite an existing file.
    """
    with open(path, "w") as fh:
        print(path, file=fh, end="")


class SuccessfulQueue(object):
    result = "yay"
    info = None
    status = 409
    reclaim_task = {
        'credentials': {'a': 'b'},
    }

    @pytest.mark.asyncio
    async def claimTask(self, *args, **kwargs):
        return self.result

    @pytest.mark.asyncio
    async def reclaimTask(self, *args, **kwargs):
        if self.info is None:
            self.info = ['reclaimTask', args, kwargs]
            return self.reclaim_task
        else:
            raise taskcluster.exceptions.TaskclusterRestFailure("foo", None, status_code=self.status)

    @pytest.mark.asyncio
    async def reportCompleted(self, *args, **kwargs):
        self.info = ['reportCompleted', args, kwargs]

    @pytest.mark.asyncio
    async def reportFailed(self, *args, **kwargs):
        self.info = ['reportFailed', args, kwargs]

    @pytest.mark.asyncio
    async def reportException(self, *args, **kwargs):
        self.info = ['reportException', args, kwargs]

    @pytest.mark.asyncio
    async def createArtifact(self, *args, **kwargs):
        self.info = ['createArtifact', args, kwargs]
        return {
            "contentType": "text/plain",
            "putUrl": "url",
        }

    @pytest.mark.asyncio
    async def pollTaskUrls(self, *args, **kwargs):
        return


class UnsuccessfulQueue(object):
    status = 409

    @pytest.mark.asyncio
    async def claimTask(self, *args, **kwargs):
        raise taskcluster.exceptions.TaskclusterFailure("foo")

    @pytest.mark.asyncio
    async def reportCompleted(self, *args, **kwargs):
        raise taskcluster.exceptions.TaskclusterRestFailure("foo", None, status_code=self.status)

    @pytest.mark.asyncio
    async def reportFailed(self, *args, **kwargs):
        raise taskcluster.exceptions.TaskclusterRestFailure("foo", None, status_code=self.status)


class FakeResponse(aiohttp.client_reqrep.ClientResponse):
    """Integration tests allow us to test everything's hooked up to aiohttp
    correctly.  When we don't want to actually hit an external url, have
    the aiohttp session's _request method return a FakeResponse.
    """
    def __init__(self, *args, status=200, payload=None, **kwargs):
        super(FakeResponse, self).__init__(*args, **kwargs)
        self._connection = mock.MagicMock()
        self._payload = payload or {}
        self.status = status
        self.headers = {'content-type': 'application/json'}
        self._loop = mock.MagicMock()

    @asyncio.coroutine
    def text(self, *args, **kwargs):
        return json.dumps(self._payload)

    @asyncio.coroutine
    def json(self, *args, **kwargs):
        return self._payload

    @asyncio.coroutine
    def release(self):
        return


@pytest.fixture(scope='function')
def successful_queue():
    return SuccessfulQueue()


@pytest.fixture(scope='function')
def unsuccessful_queue():
    return UnsuccessfulQueue()


@pytest.fixture(scope='function')
def fake_session():
    @asyncio.coroutine
    def _fake_request(method, url, *args, **kwargs):
        return FakeResponse(method, url)

    session = aiohttp.ClientSession()
    session._request = _fake_request
    return session


@pytest.fixture(scope='function')
def fake_session_500():
    @asyncio.coroutine
    def _fake_request(method, url, *args, **kwargs):
        return FakeResponse(method, url, status=500)

    session = aiohttp.ClientSession()
    session._request = _fake_request
    return session