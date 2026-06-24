# Run 3 Disappearing Tracks Analysis Dashboard

Initial Streamlit dashboard for project tracking and analysis progress.

This first milestone is intentionally small:

- SQLite-backed task storage
- overview page with automatic progress summaries
- task management page
- dataset tracking page
- data-source snapshot registry for local development with LPC-collected inputs
- snapshot-backed HTCondor monitoring page
- snapshot-backed CRAB task monitoring page
- EOS ROOT output inventory page
- idempotent seed button for standard Run 3 analysis tasks

Future milestones can add ROOT validation, plot review, and unblinding
readiness checks.

## Run Locally

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
streamlit run app.py
```

Or, if dependencies are already available:

```bash
streamlit run app.py
```

The SQLite database is created automatically at:

```text
data/dashboard.sqlite
```

## Snapshot Workflow

The dashboard is designed to run locally without direct access to LPC-only
services such as CRAB, HTCondor, or EOS. Collector scripts can be run on LPC and
write JSON snapshots into:

```text
snapshots/
```

Snapshot JSON files are ignored by git. The dashboard records their metadata on
the Data Sources page. A snapshot should use this shape:

```json
{
  "metadata": {
    "source_type": "crab",
    "label": "crab status 2025-06-23",
    "collected_at": "2025-06-23T12:00:00-05:00",
    "host": "cmslpc-el9.fnal.gov",
    "username": "USER",
    "status": "ok"
  },
  "summary": {
    "tasks": 12,
    "failed_jobs": 3
  },
  "records": []
}
```

## LPC Snapshot Sync

For automated collection, copy the example configuration and set the LPC host
and dashboard path once:

```bash
cp sync_snapshots.conf.example sync_snapshots.conf
```

The local `sync_snapshots.conf` file is ignored by git. After updating it, run
the sync wrapper from your laptop or desktop:

```bash
./sync_snapshots.sh
```

The wrapper runs this on LPC:

```bash
bash collectors/collect_all.sh
```

and then copies JSON files back into the local `snapshots/` directory with
`rsync`. The initial collectors write environment and HTCondor snapshots so the
SSH/Kerberos and copy workflow can be tested before adding CRAB and EOS commands.
SSH runs with X11 forwarding disabled for this non-interactive workflow.

Command-line environment variables override the saved configuration when a
one-off change is needed:

```bash
REMOTE_COLLECT=0 ./sync_snapshots.sh
```

If you want the LPC collector wrapper to renew a CMS proxy when less than four
hours remain during remote sync, run:

```bash
DASHBOARD_ENSURE_PROXY=1 ./sync_snapshots.sh
```

The proxy thresholds can be adjusted with:

```bash
DASHBOARD_PROXY_MIN_VALID=4:00
DASHBOARD_PROXY_VALID=192:00
```

HTCondor collection includes the active queue and the 200 most recent history
records per configured schedd by default. Adjust the history depth and LPC
schedd list in `sync_snapshots.conf`:

```bash
DASHBOARD_CONDOR_HISTORY_LIMIT=500
DASHBOARD_CONDOR_SCHEDDS=lpcschedd4.fnal.gov,lpcschedd5.fnal.gov,lpcschedd6.fnal.gov
```

CRAB tasks are discovered by default under:

```text
DisappTrks_v2/BkgdEstimation/test/crab_projects/*/*/crab_*
```

Override the discovery globs with a comma-separated value when additional CRAB
work areas need to be monitored:

```bash
DASHBOARD_CRAB_TASK_GLOBS=/path/to/workarea/crab_*,/path/to/another/crab_*
```

EOS inventory defaults to:

```text
/store/group/lpclonglived/DisappTrks
/store/group/lpcdisapptrks/ntuplizer
/store/group/lpcdisapptrks/custom_nanoaod
```

The `custom_nanoaod` directory is reserved for future production. Until it is
created, the EOS Outputs page reports it as `not_created`. Configure roots with:

```bash
DASHBOARD_EOS_ENDPOINT=root://cmseosmgm01.fnal.gov
DASHBOARD_EOS_ROOTS=/store/path/one,/store/path/two
```

## Layout

```text
analysis_dashboard/
  app.py
  collectors/
    collect_all.sh
    collect_condor_status.py
    collect_crab_status.py
    collect_environment.py
    collect_eos_outputs.py
  dashboard/
    config.py
    db.py
    progress.py
    seed.py
    schema.sql
    pages/
      condor.py
      crab.py
      datasets.py
      eos.py
      overview.py
      snapshots.py
      tasks.py
  sync_snapshots.sh
  snapshots/
```
