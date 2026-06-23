# Run 3 Disappearing Tracks Analysis Dashboard

## Project Overview

Develop a dashboard system for managing and monitoring the CMS Run 3 Disappearing Tracks analysis using data collected during 2022–2025.

The dashboard should serve two purposes:

1. **Project Management**

   * Track analysis progress.
   * Manage tasks, dependencies, and ownership.
   * Monitor readiness for review and unblinding.

2. **Production Monitoring**

   * Monitor CRAB task status.
   * Monitor HTCondor jobs.
   * Validate EOS outputs.
   * Validate ROOT files.
   * Automatically calculate analysis progress from completed deliverables.

The dashboard should minimize manual status updates by deriving status from actual artifacts whenever possible.

---

# Technology Stack

## Initial Implementation

Backend:

* Python 3.11+
* SQLite

Frontend:

* Streamlit

Data Processing:

* pandas
* uproot
* awkward
* numpy

External Interfaces:

* CRAB CLI
* HTCondor CLI
* XRootD
* EOS
* ROOT files via uproot

Version Control:

* Git
* GitHub

---

# Analysis Structure

## Eras

```yaml
2022
2023
2024
2025
```

## Backgrounds

```yaml
electron
muon
tau
fake_track
```

## Signal Categories

```yaml
NLayers4
NLayers5
NLayers6plus
```

## Lepton Background Components

```yaml
Nctrl
Pveto
Poffline
Ptrigger
closure
final_estimate
```

---

# Dashboard Pages

## 1. Overview

Purpose:
Provide a high-level summary of the entire analysis.

Display:

* Overall completion percentage
* Progress by era
* Critical blockers
* Failed CRAB tasks
* Failed Condor jobs
* Missing outputs
* Unblinding readiness

Example:

```text
Overall Progress: 63%

2022  ██████████ 100%
2023  ██████████ 100%
2024  ███████░░░  70%
2025  ███░░░░░░░  30%

Failed CRAB Tasks: 7
Missing Output Files: 12
Critical Blockers: 2
```

---

## 2. Analysis Tasks

Track all major tasks.

Fields:

```text
Task Name
Category
Era
Owner
Priority
Status
Progress
Dependencies
Last Updated
```

Statuses:

```yaml
not_started
in_progress
waiting
review
complete
blocked
```

Examples:

```text
Muon Pveto 2025
Tau Closure 2024
Trigger SF Validation 2025
```

---

## 3. Dataset Tracking

Track all datasets used in the analysis.

Fields:

```text
Era
Primary Dataset
MiniAOD Dataset
Ntuple Location
Status
Validation Status
```

Examples:

```text
Muon
EGamma
JetMET
MET
Signal MC
Background MC
```

---

## 4. CRAB Monitoring

Automatically poll CRAB tasks.

Data Source:

```bash
crab status
```

Track:

```text
Task Name
Era
Dataset
Finished Jobs
Failed Jobs
Running Jobs
Transferring Jobs
Cooloff Jobs
Status
Last Update
```

Dashboard Features:

* Search
* Filters by era
* Filters by dataset
* Show failed jobs
* Show failed job logs

Color Coding:

```yaml
green:
  all jobs finished

yellow:
  running jobs remain

red:
  failed jobs present
```

---

## 5. HTCondor Monitoring

Automatically poll Condor.

Commands:

```bash
condor_q -json
condor_history -json
```

Track:

```text
Cluster ID
Proc ID
Task Name
Status
Memory Usage
Runtime
Exit Code
```

Features:

* Running jobs
* Completed jobs
* Failed jobs
* Long-running jobs
* Memory violations

---

## 6. EOS Validation

Automatically verify expected output files.

Data Sources:

```bash
xrdfs root://eoscms.cern.ch ls
xrdfs root://cmseos.fnal.gov ls
```

Track:

```text
Expected Files
Found Files
Missing Files
File Size
Modification Time
```

Display:

```text
Dataset Complete
Dataset Incomplete
Missing Outputs
```

---

## 7. ROOT File Validation

Validate output ROOT files.

Use:

```python
uproot
```

Checks:

```text
File opens successfully
Required trees exist
Required histograms exist
Entries > 0
Required branches exist
```

Store:

```text
File Path
Validation Status
Tree Name
Entries
Missing Branches
```

Validation Result:

```yaml
valid
warning
failed
```

---

## 8. Background Estimation Tracking

Track progress for:

```yaml
electron
muon
tau
fake_track
```

Each era should track:

```text
Nctrl
Pveto
Poffline
Ptrigger
Closure
Final Estimate
```

Example:

```text
Muon Background 2025

Nctrl         Complete
Pveto         Complete
Poffline      In Progress
Ptrigger      Not Started
Closure       Not Started
```

---

## 9. Systematics Tracking

Track all systematic uncertainty studies.

Examples:

```yaml
pileup
trigger
ISR
tracking
missing_hits
background_estimate
```

Track by era.

Status:

```yaml
not_started
running
validated
finalized
```

---

## 10. Plot Validation

Store and track approval status of plots.

Fields:

```text
Plot Name
Era
Category
Status
Reviewer
Comments
```

Statuses:

```yaml
draft
review
approved
rejected
```

---

## 11. Unblinding Readiness

Automatically determine readiness.

Requirements:

```text
All backgrounds finalized
All systematics finalized
Signal acceptance finalized
Documentation complete
Validation complete
```

Display:

```text
Ready to Unblind: YES / NO
```

List blocking items.

---

# Database Schema

## tasks

```sql
id
name
category
era
owner
priority
status
progress
depends_on
created_at
updated_at
```

## datasets

```sql
id
era
primary_dataset
miniAOD_dataset
ntuple_path
status
validation_status
```

## crab_tasks

```sql
id
name
era
dataset_id
status
finished_jobs
failed_jobs
running_jobs
transferring_jobs
cooloff_jobs
last_checked
```

## condor_jobs

```sql
id
cluster_id
proc_id
task_name
status
memory_mb
runtime_sec
exit_code
last_checked
```

## output_files

```sql
id
dataset_id
path
exists
size_bytes
root_valid
tree_name
entries
last_checked
```

## background_estimates

```sql
id
background
era
component
category
value
uncertainty
status
```

---

# Automatic Progress Calculation

Progress should be derived automatically whenever possible.

Example:

Muon Background 2025

Weights:

```yaml
Nctrl: 20
Pveto: 30
Poffline: 20
Ptrigger: 20
Closure: 10
```

If Nctrl and Pveto are complete:

```text
Progress = 50%
```

Overall analysis progress should be computed from weighted subtasks.

---

# Development Roadmap

## Milestone 1

Build:

* Streamlit application
* SQLite database
* Task management
* Overview page
* Automatic progress calculations

## Milestone 2

Add:

* CRAB polling
* CRAB dashboard
* Failed task tracking

## Milestone 3

Add:

* EOS validation
* Dataset completeness monitoring

## Milestone 4

Add:

* ROOT validation
* Dataset quality monitoring

## Milestone 5

Add:

* HTCondor monitoring
* Runtime diagnostics
* Failure classification

## Milestone 6

Add:

* Plot review workflow
* Unblinding readiness page
* Documentation tracking

---

# Design Goals

1. Reduce manual bookkeeping.
2. Derive status from actual outputs whenever possible.
3. Make failures immediately visible.
4. Provide a single source of truth for the analysis.
5. Support multi-year Run 3 datasets.
6. Scale to additional eras and future analyses.
7. Be simple enough for collaborators to use without training.
