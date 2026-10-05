"""Cancel one identified pending duplicate, preserving the original QA run."""
import json
from qa_recover_stalled import gh

REPO = 'mwqwf/rafiq-align-ci'
ORIGINAL = 37383715985
DUPLICATE = 37383836839
TITLE = 'free-post-stage timings-staging/hafs/peshawa.aa1473cd.jz'
WORKFLOW = '.github/workflows/free-post-stage-quality.yml'


def eligible(original, duplicate, jobs):
    def identity(run, ident):
        return (run.get('id') == ident and run.get('path') == WORKFLOW
                and run.get('display_title') == TITLE
                and run.get('event') == 'workflow_dispatch'
                and run.get('repository', {}).get('full_name') == REPO
                and run.get('repository', {}).get('private') is False)
    return (identity(original, ORIGINAL) and identity(duplicate, DUPLICATE)
            and (original.get('status') == 'in_progress'
                 or original.get('status') == 'completed' and original.get('conclusion') == 'success')
            and duplicate.get('status') in ('pending', 'queued')
            and duplicate.get('created_at', '') > original.get('created_at', '')
            and all(j.get('status') in ('queued', 'pending', 'waiting') for j in jobs))


def main():
    original = gh(f'actions/runs/{ORIGINAL}')
    duplicate = gh(f'actions/runs/{DUPLICATE}')
    jobs = gh(f'actions/runs/{DUPLICATE}/jobs')['jobs']
    ok = eligible(original, duplicate, jobs)
    print(json.dumps({'original': ORIGINAL, 'duplicate': DUPLICATE,
                      'duplicateStatus': duplicate['status'], 'eligible': ok}))
    if ok:
        gh(f'actions/runs/{DUPLICATE}/cancel', {})
        print('Cancellation requested for pending duplicate only')
    elif duplicate.get('status') != 'completed':
        raise ValueError('Duplicate identity or unstarted status no longer matches; no cancellation')


if __name__ == '__main__':
    main()
