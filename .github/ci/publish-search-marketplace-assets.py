#!/usr/bin/env python3
"""Verify and add reviewed v2 search/marketplace assets; never promote a release."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile
import zipfile
from io import BytesIO

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / 'release-candidates/v2.0.0-search-marketplace-assets'
REPO = 'chonamdoo/agents-memory-releases'
TAG = 'v2.0.0'
PROOF = 'SEARCH-MARKETPLACE-SOURCE-VERIFICATION.json'
SUMS = 'SEARCH-MARKETPLACE-SHA256SUMS'
BUNDLE = 'agents-memory-unified-2.0.0-search-calibrated.tar.gz'
PLUGIN = 'agents-memory-unified-plugin-2.0.0.zip'
FILES = {BUNDLE, PLUGIN, PROOF, SUMS, 'SUBMISSION.ko.md'}
MARKER = '<!-- search-marketplace-update-20261107 -->'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def safe(name):
    path = PurePosixPath(name)
    return not path.is_absolute() and '..' not in path.parts


def verify():
    need({p.name for p in PAYLOAD.iterdir()} == FILES, 'Unexpected payload file set')
    need(all(p.is_file() and not p.is_symlink() for p in PAYLOAD.iterdir()), 'Invalid payload type')
    rows = [line.split('  ', 1) for line in (PAYLOAD / SUMS).read_text().splitlines()]
    hashes = dict((name, value) for value, name in rows)
    need(len(rows) == len(hashes) and set(hashes) == FILES - {SUMS}, 'Invalid checksum manifest')
    for name, expected in hashes.items():
        need(digest((PAYLOAD / name).read_bytes()) == expected, f'Checksum mismatch: {name}')
    proof = json.loads((PAYLOAD / PROOF).read_text())
    need(proof['channel'] == 'prerelease' and proof['external_jev_calls'] == 0, 'Invalid evidence scope')
    with tarfile.open(PAYLOAD / BUNDLE) as bundle:
        members = bundle.getmembers()
        need(all(m.isfile() and safe(m.name) for m in members), 'Unsafe archive member')
        need(len({m.name for m in members}) == len(members), 'Duplicate archive member')
        manifest = json.load(bundle.extractfile('ASSETS.json'))
        need(manifest['version'] == '2.0.0', 'Wrong runtime version')
        need({m.name for m in members} == set(manifest['files']) | {'ASSETS.json'}, 'Unexpected archive files')
        for name, expected in manifest['files'].items():
            need(digest(bundle.extractfile(name).read()) == expected, f'Internal checksum: {name}')
        for field in ('core_312', 'core_313', 'sdk'):
            raw = bundle.extractfile(manifest[field]).read()
            with zipfile.ZipFile(BytesIO(raw)) as wheel:
                if field == 'sdk':
                    need(digest(raw) == proof['sdk_wheel_sha256'], 'SDK wheel changed')
                    python = [name for name in wheel.namelist() if name.endswith('.py')]
                    need(len(python) == 15, 'Unexpected SDK source file set')
                    for name in python:
                        need(wheel.read(name) == (ROOT / 'distribution/server/src' / name).read_bytes(), 'Tested SDK source changed')
                else:
                    expected_core = {'core_312': '48406a54f4bc78b0276d0550369e140013cc270b5ef9fe13576fb3f22bdb4d14', 'core_313': '1c5de9e8be3446acf12b08a41e18b2f2ab451058ae8302a8ef4cc2690c812bf9'}
                    need(digest(raw) == expected_core[field], 'Original published Core wheel changed')
                    need(all(not name.endswith(('.c', '.h')) and (not name.endswith('.py') or name in {
                        'agents_memory/__init__.py', 'agents_memory/runtime_launcher.py'
                    }) for name in wheel.namelist()), 'Private source in Core wheel')
    plugin = ROOT / 'plugins/agents-memory-unified'
    with zipfile.ZipFile(PAYLOAD / PLUGIN) as archive:
        need(archive.testzip() is None, 'Corrupt plugin ZIP')
        names = archive.namelist()
        need(len(names) == len(set(names)) and all(safe(n) for n in names), 'Unsafe plugin paths')
        need(set(names) == {str(p.relative_to(plugin)) for p in plugin.rglob('*') if p.is_file()}, 'Unexpected plugin file set')
        for name in names:
            need(archive.read(name) == (plugin / name).read_bytes(), 'Reviewed plugin changed')
    return proof


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def release():
    return json.loads(gh('api', f'repos/{REPO}/releases/tags/{TAG}'))


def preserve_originals(current, proof):
    actual = {a['name']: a for a in current['assets']}
    for old in proof['original_release_assets_preserved']:
        need(old['name'] in actual, 'Original release asset missing')
        need(all(actual[old['name']].get(k) == old.get(k) for k in ('id', 'size', 'digest')), 'Original release asset changed')


def publish(proof):
    before = release()
    need(before['id'] == 437252762 and before['prerelease'] and not before['draft'], 'Expected published prerelease')
    preserve_originals(before, proof)
    existing = {a['name']: a for a in before['assets']}
    for name in sorted(FILES):
        expected = 'sha256:' + digest((PAYLOAD / name).read_bytes())
        if name in existing:
            need(existing[name].get('digest') == expected, f'Existing asset differs: {name}')
        else:
            subprocess.run(['gh', 'release', 'upload', TAG, str(PAYLOAD / name), '--repo', REPO], check=True)
    current = release()
    preserve_originals(current, proof)
    need(current['prerelease'] == before['prerelease'], 'Release channel changed concurrently')
    if MARKER not in current['body']:
        note = f'''\n\n{MARKER}
## 2026-11-07 검색 수정·마켓 배포 추가

새 검색 수정 런타임은 `{BUNDLE}`, 플러그인 패키지는 `{PLUGIN}`입니다.
이 추가 파일들은 `{SUMS}`로 검증하세요. 기존 `SHA256SUMS`는 원래 시험판 파일용입니다.
출처·검증 범위는 `{PROOF}`와 `SUBMISSION.ko.md`를 확인하세요. 모델 companion은 기존과 같습니다.

검색 개발 세트에서만 기준을 선택한 뒤 고정한 검증 40/40 Hit@5, 필수 근거 전체 회수 38/40,
무관 질의 12/12 빈 결과를 확인했고 SDK·평가기 278 통과/0 실패/1 건너뜀입니다.
이는 단일 작성자 합성 자료의 검색 공학 검증이며 실제 Jev 저장 품질 재검증이나 독립 인적 평가는 아닙니다.
기존 v43 결과와 정당한 명시 저장 70/80 실패 기록을 보존합니다. 정식 전환은 아직 하지 않았습니다.

자체 공개 마켓 `chonamdoo/agents-memory-releases`에서 `agents-memory-unified@agents-memory` 2.0.0을 제공합니다.
Claude·OMP는 플러그인 MCP, Codex는 전용 설치 skill과 프로젝트 MCP 설치기를 사용합니다.
공개 주소에서 세 호스트의 마켓 설치를 확인했습니다. 마켓 설치 자체가 엔진 준비 완료를 뜻하지 않습니다.
중앙 Anthropic/OpenAI 디렉터리 등재는 완료되지 않았습니다.
'''
        with tempfile.TemporaryDirectory() as temp:
            request = Path(temp) / 'release-update.json'
            request.write_text(json.dumps({'body': current['body'] + note}, ensure_ascii=False))
            gh('api', '--method', 'PATCH', f'repos/{REPO}/releases/{current["id"]}', '--input', str(request))
    after = release()
    preserve_originals(after, proof)
    need(after['prerelease'] == before['prerelease'], 'Release channel changed')
    print(json.dumps({'published_assets': sorted(FILES), 'prerelease': after['prerelease'], 'original_assets_preserved': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    proof = verify()
    print('PASS: checked archives, source-free Core, tested SDK, reviewed plugin and checksums')
    if args.publish:
        publish(proof)
