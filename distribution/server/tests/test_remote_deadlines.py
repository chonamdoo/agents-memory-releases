"""Completed backend recall must fit the actual stdio client's request deadline."""
import io
import json
from types import SimpleNamespace

import pytest

from agents_memory_collab.client import Remote
from agents_memory_collab.stdio import LocalMCP


class ModelRead:
    """Model a reply arriving after 10s without sleeping in a regression test."""
    def __init__(self):
        self.deadlines = []

    def open(self, request, *, timeout):
        self.deadlines.append((request.full_url, timeout))
        if request.full_url.endswith('/v1/recall') and timeout is not None and timeout < 30:
            raise TimeoutError('backend reply has not arrived at the client deadline')
        return io.BytesIO(json.dumps({'memories':[{'text':'The complete server-side source.'}]}).encode())


async def test_stdio_recall_waits_for_bounded_backend_instead_of_false_offline_empty():
    remote=Remote('http://127.0.0.1:18350','amc_'+'a'*43)
    remote.http=ModelRead()
    replica=SimpleNamespace(remote=remote,status=lambda:{'memory_contract':'agents-memory-grounded-v1'},
                            list_memories=lambda project:[])
    result=await LocalMCP(replica,'synthetic').recall({'project':'synthetic','query':'What is the source?'})
    assert result['source']=='server'
    assert result['memories']==[{'text':'The complete server-side source.'}]
    assert 120 < remote.http.deadlines[0][1] <= 150


def test_search_deadline_does_not_extend_setup_sync_or_original_search():
    remote=Remote('http://127.0.0.1:18350','amc_'+'a'*43)
    remote.http=ModelRead()
    for path in ['/v1/me','/v1/sync/changes','/v1/sources/search']:
        remote.request(path,{})
    remote.request('/v1/teams/11111111-1111-1111-1111-111111111111/search',{})
    assert [timeout for _,timeout in remote.http.deadlines[:3]]==[10,10,10]
    assert 120 < remote.http.deadlines[3][1] <= 150


def test_explicit_caller_deadline_still_controls_recall():
    remote=Remote('http://127.0.0.1:18350','amc_'+'a'*43,timeout=.25)
    remote.http=ModelRead()
    with pytest.raises(TimeoutError):remote.request('/v1/recall',{})
    assert remote.http.deadlines[0][1]==.25
