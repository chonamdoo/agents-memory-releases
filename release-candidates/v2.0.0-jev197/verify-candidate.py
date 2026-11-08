"""Check this prerelease and exported receipts; never approve stable promotion."""
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import tarfile
import xml.etree.ElementTree as ET
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(directory):
    proof=json.loads((directory/'VERIFICATION.json').read_text())
    archive=directory/proof['archive']['name']
    data=archive.read_bytes()
    assert sha(data)==proof['archive']['sha256']
    assert (directory/'JEV197-SHA256SUMS').read_text()==sha(data)+'  '+archive.name+'\n'
    root=directory.parents[1]
    allowed={'agents_memory/__init__.py','agents_memory/runtime_launcher.py'}
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
        members=tar.getmembers()
        assert len({m.name for m in members})==len(members)
        assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
        manifest=json.load(tar.extractfile('ASSETS.json'))
        assert manifest['version']==proof['runtime_version']=='2.0.0'
        assert {m.name for m in members}==set(manifest['files'])|{'ASSETS.json'}
        for name,digest in manifest['files'].items():
            assert sha(tar.extractfile(name).read())==digest,name
        for tag,label in [('cp312','core_312'),('cp313','core_313')]:
            body=tar.extractfile(manifest[label]).read()
            pin=proof['core_wheels'][tag]
            assert sha(body)==pin['sha256']
            with zipfile.ZipFile(io.BytesIO(body)) as wheel:
                assert all(not n.endswith(('.c','.h')) and (not n.endswith('.py') or n in allowed) for n in wheel.namelist())
                actual={n:sha(wheel.read(n)) for n in wheel.namelist() if n.startswith('agents_memory/') and n.endswith('.pyc')}
                assert len(actual)==13 and actual==pin['modules']
        sdk=tar.extractfile(manifest['sdk']).read()
        assert sha(sdk)==proof['sdk_wheel_sha256']
        with zipfile.ZipFile(io.BytesIO(sdk)) as wheel:
            modules=[n for n in wheel.namelist() if n.startswith('agents_memory_collab/') and n.endswith('.py')]
            assert len(modules)==15
            for name in modules+['agents_memory_collab/schema.sql']:
                assert wheel.read(name)==(root/'distribution/server/src'/name).read_bytes(),name
        for name in ('install-client.sh', 'install-unified.sh', 'unified_setup.py'):
            assert tar.extractfile(name).read()==(root/'distribution/server'/name).read_bytes(),name
    budget=json.loads((directory/'BUDGET.json').read_text())
    assert budget['reserved_attempts']==budget['cap']==len(budget['attempts'])==197
    assert [r['ordinal'] for r in budget['attempts']]==list(range(1,198))
    assert len({r['request_hash'] for r in budget['attempts']})==197
    assert all(r['stage']=='completed' and r['result']['failure'] is None
               and r['result']['dispatch_started'] is True for r in budget['attempts'])
    cohort=json.loads((directory/'COHORT.json').read_text())
    assert cohort['case_count']==196 and cohort['question_count']==40
    assert cohort['independent_human_labels'] is False and cohort['classification_kappa'] is None
    decisions=json.loads((directory/'ADMISSION-DECISIONS.json').read_text())
    assert len(decisions)==len({r['cid'] for r in decisions})==196
    assert sum(r['new_attempts'] for r in decisions)==194
    assert sum(r['decision']=='guarded' for r in decisions)==2
    baseline=json.loads((directory/'ADMISSION-SUMMARY.json').read_text())
    assert baseline['legitimate_explicit_stored']['successes']==79
    assert baseline['legitimate_explicit_stored']['denominator']==80
    assert baseline['stable_approval'] is False and baseline['stop'] is None
    targeted=json.loads((directory/'TARGETED-RESULTS.json').read_text())
    assert targeted['reserved_attempts']==197 and targeted['all_expected'] is True
    assert [r['decision'] for r in targeted['results']]==['keep','review']
    session=json.loads((directory/'SESSION-BUDGET.json').read_text())
    registration=json.loads((directory/'SESSION-GRANT.json').read_text())
    assert session['approved_cumulative_cap']==registration['maximum_reserved_attempts']==1000
    assert len(session['grants'])==len(registration['grants'])
    reserved=allocated=failures=0
    for exported,registered in zip(session['grants'],registration['grants']):
        assert all(exported[name]==registered[name] for name in ['name','cap','grant_file','grant_sha256'])
        grant=json.loads((directory/exported['grant_file']).read_text())
        canonical=json.dumps(grant,sort_keys=True,separators=(',',':'),ensure_ascii=False)
        assert sha(canonical.encode())==exported['grant_sha256']
        journal=json.loads((directory/exported['budget_file']).read_text())
        assert 1<=exported['cap']<=197 and grant['cap']==exported['cap']
        count=journal['reserved_attempts']
        assert count==exported['reserved_attempts']==len(journal['attempts'])<=journal['cap']==exported['cap']
        assert [row['ordinal'] for row in journal['attempts']]==list(range(1,count+1))
        assert len({row['request_hash'] for row in journal['attempts']})==count
        assert all(row['stage'] in {'completed','failed'} for row in journal['attempts'])
        failures+=sum(row['result']['failure'] is not None for row in journal['attempts'])
        reserved+=count;allocated+=journal['cap']
    assert reserved==session['reserved_attempts']<=allocated<=1000
    # Installer reservations are conservative process bounds; failed pre-network
    # attempts consume their slot and are not represented as typed Jev responses.
    assert failures>=1
    development=json.loads((directory/'V16-FULL-DEVELOPMENT.json').read_text())
    assert development['completed']==196 and development['stop'] is None
    assert development['legitimate_explicit_kept']['successes']==80
    fresh=json.loads((directory/'FRESH-ADMISSION.json').read_text())
    assert fresh['completed']==196 and fresh['stop'] is None and fresh['reserved_attempts']==194
    assert fresh['legitimate_explicit_stored']['successes']==80
    assert fresh['classified_negative_keeps']==[] and fresh['provider_audit_count']==194
    assert fresh['independent_label_kappa'] is None and fresh['label_author_count']==1
    assert json.loads((directory/'FRESH-FAILED-INTEGRATION.json').read_text())['success'] is False
    storage=json.loads((directory/'FRESH-STORAGE.json').read_text())
    assert storage['completed']==196 and storage['committed']==storage['native_documents_verified']==120
    assert storage['legitimate_explicit_committed']==storage['explicit_denominator']==80
    assert storage['all_storage_matches_live_admission'] and storage['new_jev_calls']==0
    final=json.loads((directory/'FINAL-VALIDATION.json').read_text())
    assert final['sdk_wheel_sha256']==proof['sdk_wheel_sha256']
    for check in final['checks']:
        body=(directory/check['path']).read_bytes()
        assert sha(body)==check['sha256']
        parsed=ET.fromstring(body)
        suites=[parsed] if parsed.tag=='testsuite' else list(parsed.iter('testsuite'))
        for key in ('tests','failures','errors','skipped'):
            assert sum(int(s.attrib.get(key,0)) for s in suites)==check[key]
        assert check['tests'] in (322,59)
        assert check['failures']==check['errors']==check['skipped']==0
    assert len(final['checks'])==3
    assert {tag:pin['sha256'] for tag,pin in proof['core_wheels'].items()}==final['core_wheels']
    assert all(sha((root/name).read_bytes())==digest for name,digest in final['source_files_sha256'].items())
    for tag in ('cp312','cp313'):
        report=json.loads((directory/(tag.upper()+'-V16-RUNTIME.json')).read_text())
        assert report['sdk_wheel_sha256']==proof['sdk_wheel_sha256']
        assert len(report['core_modules'])==13 and len(report['sdk_modules'])==15
        assert report['network_connections_forbidden'] and report['probe_external_jev_calls']==0
    for name in ('SERIAL-RERANKER-SOURCE.xml','SERIAL-RERANKER-WHEEL312.xml','SERIAL-RERANKER-WHEEL313.xml'):
        suites=list(ET.fromstring((directory/name).read_bytes()).iter('testsuite'))
        assert sum(int(s.attrib.get('tests',0)) for s in suites)==38
        assert sum(int(s.attrib.get(key,0)) for s in suites for key in ('failures','errors','skipped'))==0
    failed_search=json.loads((directory/'FRESH-BASELINE-RETRIEVAL.json').read_text())
    assert failed_search['retrieval_completed']==40
    assert failed_search['hit5_any_relevant']['successes']==32
    assert failed_search['all_three_required_evidence']['successes']==6
    assert failed_search['top5_noise']['irrelevant_occurrences']==134
    assert failed_search['top5_noise']['actual_returned_occurrences']==200
    repair=json.loads((directory/'QUESTION-REPAIR-PLAN.json').read_text())
    assert repair['original40_preserved'] and repair['frozen_before_first_corrected_query']
    assert repair['changed_questions']==len(repair['corrections'])==10
    assert repair['unchanged_questions']==30
    final_retrieval=json.loads((directory/'FINAL-RETRIEVAL.json').read_text())
    assert final_retrieval['identity']['sdk_wheel_sha256']==proof['sdk_wheel_sha256']
    assert final_retrieval['identity']['core_wheel_sha256']==proof['core_wheels']['cp312']['sha256']
    assert final_retrieval['query_count']==len(final_retrieval['items'])==40
    assert len({item['qid'] for item in final_retrieval['items']})==40
    assert final_retrieval['cross_candidate_response_reuse']==final_retrieval['new_jev_calls']==0
    assert final_retrieval['corrected_original_questions']==10
    assert not final_retrieval['original_independent_contract_satisfied']
    assert not final_retrieval['source_search_scores_substituted_for_recall']
    for key,field in [('hit5_any_relevant','hit5_any'),('all_required_complete_passages','all_required')]:
        assert final_retrieval[key]['successes']==sum(item[field] for item in final_retrieval['items'])
        assert final_retrieval[key]['denominator']==40
    noise=final_retrieval['top5_noise']
    assert noise['irrelevant_occurrences']==sum(item['noise_occurrences'] for item in final_retrieval['items'])
    assert noise['actual_returned_occurrences']==sum(item['returned_source_occurrences'] for item in final_retrieval['items'])
    def wilson(k,n):
        z=1.959963984540054;p=k/n;denominator=1+z*z/n
        center=(p+z*z/(2*n))/denominator
        radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
        return [max(0.,center-radius),min(1.,center+radius)]
    for metric in (final_retrieval['hit5_any_relevant'],final_retrieval['all_required_complete_passages']):
        assert all(abs(a-b)<1e-12 for a,b in zip(metric['wilson95'],wilson(metric['successes'],40)))
    noise_interval=wilson(noise['irrelevant_occurrences'],noise['actual_returned_occurrences'])
    assert all(abs(a-b)<1e-12 for a,b in zip(noise['wilson95'],noise_interval))
    assert final_retrieval['engineering_numeric_thresholds_met']==(
        final_retrieval['hit5_any_relevant']['wilson95'][0]>=.75 and noise_interval[1]<=.30)
    isolated=json.loads((directory/'FINAL-ISOLATED-RESULT.json').read_text())
    assert isolated['exit_code']==isolated['external_jev_calls']==0 and isolated['network']=='none'
    limits=isolated['final_limits'];quota,period=map(int,limits['cpu.max'].split())
    assert quota==2*period and limits['memory.max']=='4294967296' and limits['memory.swap.max']=='0'
    audit=json.loads((directory/'FINAL-RESOURCE-AUDIT.json').read_text())
    events=dict(line.split() for line in audit['memory.events'].splitlines())
    assert audit['result_seen'] and events['oom']==events['oom_kill']=='0'
    container=json.loads((directory/'FINAL-CONTAINER-RUNTIME.json').read_text())
    assert container['sdk_wheel_sha256']==proof['sdk_wheel_sha256']
    assert container['core_312_wheel_sha256']==proof['core_wheels']['cp312']['sha256']
    assert len(container['core_modules'])==13 and len(container['sdk_modules'])==15
    assert not any(proof[name] for name in ['validation_ready','ready_to_promote','stable_published'])
    return {'candidate_verified':True,'reserved_jev_attempts':reserved,'remaining_cumulative_budget':1000-reserved,'failed_reservations_preserved':failures,'baseline_explicit':'79/80',
            'targeted_development_checks':2,'independent_human_labels':False,'stable_approval':False}


if __name__=='__main__':
    try:
        print(json.dumps(verify(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent),sort_keys=True))
    except (OSError,ValueError,KeyError,TypeError,AssertionError) as error:
        print('Candidate verification failed: '+str(error),file=sys.stderr)
        raise SystemExit(1)
