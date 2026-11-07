"""Verify or add the reviewed source-search assets to the existing prerelease.

Local command only; does not dispatch Actions, promote, retag or replace assets.
Uses normal gh authentication for api.github.com and uploads.github.com.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / 'release-candidates/v2.0.0-source-search'
REPO = 'chonamdoo/agents-memory-releases'
TAG = 'v2.0.0'
RELEASE_ID = 437252762
MARKER = '<!-- source-search-release-assets-20261107 -->'


def need(condition, message):
    if not condition:
        raise ValueError(message)


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def release():
    value = json.loads(gh('api', f'repos/{REPO}/releases/tags/{TAG}'))
    need(value['id'] == RELEASE_ID and value['tag_name'] == TAG,
         'Unexpected release identity')
    need(value['prerelease'] is True and value['draft'] is False,
         'Expected existing public prerelease; never change its channel')
    return value


def files():
    proof = json.loads((PAYLOAD / 'VERIFICATION.json').read_text())
    archive = PAYLOAD / proof['archive']['name']
    subprocess.run([sys.executable, str(PAYLOAD / 'verify.py'), str(archive)], check=True)
    return {archive.name: archive,
            'SOURCE-SEARCH-SHA256SUMS': PAYLOAD / 'SOURCE-SEARCH-SHA256SUMS',
            'SOURCE-SEARCH-VERIFICATION.json': PAYLOAD / 'VERIFICATION.json'}


def fingerprint(path):
    need(path.is_file() and not path.is_symlink(), 'Expected reviewed regular file')
    return {'digest': 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest(),
            'size': path.stat().st_size}


def plan(current, selected):
    existing = {asset['name']: asset for asset in current['assets']}
    need(len(existing) == len(current['assets']), 'Duplicate existing asset names')
    pending = []
    for name, path in selected.items():
        expected = fingerprint(path)
        if name in existing:
            need(all(existing[name].get(k) == v for k, v in expected.items()),
                 f'Existing asset differs; refusing to replace: {name}')
        else:
            pending.append(name)
    return pending


def preserved(before, after):
    current = {asset['name']: asset for asset in after['assets']}
    for asset in before['assets']:
        need(asset['name'] in current and all(current[asset['name']].get(k) == asset.get(k)
             for k in ('id', 'size', 'digest')), 'A previous release asset changed')


def publish(before, selected):
    pending = plan(before, selected)
    with tempfile.TemporaryDirectory() as directory:
        for name in pending:
            # gh's # suffix sets a label, not the asset's name. Stage the exact
            # public filename even when the reviewed source has another name.
            staged = Path(directory) / name
            shutil.copyfile(selected[name], staged)
            # No --clobber: an independently uploaded or differing asset fails closed.
            subprocess.run(['gh', 'release', 'upload', TAG, str(staged),
                            '--repo', REPO], check=True)
    after = release()
    preserved(before, after)
    need(not plan(after, selected), 'Uploaded asset identity could not be verified')
    if MARKER not in after['body']:
        note = f'''{MARKER}
## 원문 독립 검색 후보: 릴리즈 자산 게시 완료

최신 후보는 `agents-memory-unified-2.0.0-source-search.tar.gz`입니다.
`SOURCE-SEARCH-SHA256SUMS`와 `SOURCE-SEARCH-VERIFICATION.json`으로 검증하세요.
아래의 HTTP 401 업로드 대기 설명은 이전 실행 기록입니다. 해당 후보를 이제
이 릴리즈의 자산 목록에서 받을 수 있습니다. 기존 자산과 모델 companion은 유지했습니다.

서버와 MCP 클라이언트 양쪽을 갱신해야 `source_search`를 사용할 수 있습니다.
원문 검색은 실제 Jev 품질 기준 통과를 뜻하지 않으며 v2.0.0은 여전히 prerelease입니다.
실제 호출 수는 과거 검증 기록과 구분해 해당 평가 원장에서 확인하세요.

'''
        with tempfile.TemporaryDirectory() as directory:
            request = Path(directory) / 'release.json'
            request.write_text(json.dumps({'body': note + after['body']}, ensure_ascii=False))
            gh('api', '--method', 'PATCH', f'repos/{REPO}/releases/{RELEASE_ID}',
               '--input', str(request))
    final = release()
    preserved(before, final)
    need(not plan(final, selected) and MARKER in final['body'], 'Publication not confirmed')
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    selected = files()
    before = release()
    pending = plan(before, selected)
    if args.publish:
        publish(before, selected)
    print(json.dumps({'verified': True, 'repository': REPO, 'tag': TAG,
                      'assets': list(selected), 'pending_before': pending,
                      'published': args.publish, 'prerelease': True}))


if __name__ == '__main__':
    main()
