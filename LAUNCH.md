# Launching and monitoring the V2 run

Everything here runs from **Windows PowerShell** via `multipass`. No SSH, no VS Code, no
terminal on the VM. Written to be read after you have closed everything.

**Companion pages:** `RESUME.md` is the fuller operator guide (what to do if it dies, how
to analyse the results). This page is just launch and monitor.

---

## How the run knows to use v2 agents

It is **not** on the command you type. `systemctl start tournament` runs whatever the
unit file says, and the version is baked into that:

```ini
ExecStart=/usr/bin/python3 -m experiments.tournament \
          --games all --configs all --trials 25 --agent-version v2 --out results/v2
```

`--agent-version v2` selects `agents/v2/` and `evaluation/v2/`. The default when the flag
is absent is **v1**, deliberately, so an old command line still reproduces the v1 run.

Because that is invisible from the start command, `status.sh` prints the version from
**three independent sources** and shouts if they disagree:

```
 version : unit=v2  recorded=v2  in data=v2   (expect v2)
```

| Source | Means |
|---|---|
| `unit` | What the systemd unit is configured to run |
| `recorded` | What the process wrote into `run_meta.json` at startup |
| `in data` | What the finished games in `games.csv` were actually played with |

`-` means "nothing written yet" and is normal before the first game. Anything other than
`v2` in any column prints a **WRONG AGENT VERSION** block telling you to stop. Check it
in the first few minutes — that is the whole point of it existing.

---

## Step 0 — push (optional)

From the SSH terminal **before** you close it. Not required for the run.

```bash
git push origin plan-refinement
```

## Step 1 — close VS Code

Do this **before** starting. It frees ~1.5 GB and removes the extension host's CPU
bursts. On Isolation-hard a 4 ms spike is 20% of the 0.02 s budget, so this measurably
cleans the timing tail.

## Step 2 — start

```powershell
multipass exec tournament -- sudo systemctl start tournament
```

## Step 3 — confirm, after about a minute

```powershell
multipass exec tournament -- /home/ubuntu/search-agents-strategy-games/status.sh
```

You are looking for all four of these:

```
 service : active (enabled)   restarts: 0
 version : unit=v2  recorded=v2  in data=v2   (expect v2)
 output  : /home/ubuntu/search-agents-strategy-games/results/v2
 progress: <a rising number> / 2700 games
 >>> Healthy. Nothing to do.
```

If it says `NOT RUNNING` with `0 / 2700`, the start did not take — run step 2 again.

---

## Monitoring

That one command is the entire interface. Read the `>>>` line; it tells you what to do.

```powershell
multipass exec tournament -- /home/ubuntu/search-agents-strategy-games/status.sh
```

Refresh every 60 s (Ctrl-C to stop; read-only and safe):

```powershell
while ($true) { clear; multipass exec tournament -- /home/ubuntu/search-agents-strategy-games/status.sh; sleep 60 }
```

| Verdict | What it means | Do this |
|---|---|---|
| `Healthy` | Running normally | Nothing |
| `NOT RUNNING` | Stopped, or never started | `multipass exec tournament -- sudo systemctl start tournament` |
| `SLOW` | No game finished for 15+ min | Wait 10 min and re-check. A long Ataxx-easy game legitimately takes ~600 s |
| `STALLED` | Nothing for 30+ min | `multipass exec tournament -- sudo systemctl restart tournament` — safe, resume is crash-safe |
| `FAILED` | Crashed 5x in 10 min, systemd gave up | Read the log first, below |
| `RESTART LOOP WARNING` | 3+ restarts | Compare the game count across two checks 10 min apart |
| `WRONG AGENT VERSION` | The run is not v2 | **Stop immediately.** See below |
| `COMPLETE` | 2700/2700 | Go to `RESUME.md` section 6 |

### Reading the logs

```powershell
multipass exec tournament -- tail -60 /home/ubuntu/search-agents-strategy-games/results/tournament.log
multipass exec tournament -- sudo journalctl -u tournament -n 100 --no-pager
```

### On `FAILED`

The unit stops itself after 5 crashes in 10 minutes, deliberately — a deterministic crash
would otherwise spin all night. Capture the evidence first (above), then:

```powershell
multipass exec tournament -- sudo systemctl reset-failed tournament
multipass exec tournament -- sudo systemctl start tournament
```

### On `WRONG AGENT VERSION`

```powershell
multipass exec tournament -- sudo systemctl stop tournament
multipass exec tournament -- sudo cat /etc/systemd/system/tournament.service
```

Fix `ExecStart`, then **delete the partial output before restarting** — resume would keep
the games already played with the wrong version:

```powershell
multipass exec tournament -- rm -rf /home/ubuntu/search-agents-strategy-games/results/v2
multipass exec tournament -- sudo systemctl start tournament
```

### Telling a real restart loop from ordinary restarts

Run `status.sh` twice, ten minutes apart, and compare the **game count**.

- Rising → it is making progress. Leave it alone even if restarts are nonzero.
- Identical while restarts climb → it is crashing on the same game every time. Read the
  log before restarting.

### If the VM itself is gone

```powershell
multipass list
multipass start tournament     # the service is enabled, so it resumes on boot
```

---

## Two things to expect

**Trust ~9.9 h, not the early rate.** Isolation runs first and is fast, so the first
hour extrapolates to a wildly optimistic ETA. `status.sh` says so on screen.

**Isolation results will look much like V1's.** The one behaviour change in v2 — the
one-ply heuristic no longer declining an immediate win — was measured over 720 games per
version and moved heuristic-vs-random only from 0.750 [0.666, 0.819] to 0.767
[0.683, 0.833]. V2's value is the instrumentation, the versioning and the tighter
25-trial intervals that v3 will be measured against, not new findings about the agents.

---

## When it finishes

`status.sh` prints `COMPLETE` at 2700/2700. Then, from PowerShell:

```powershell
multipass exec tournament -- bash -c "cd search-agents-strategy-games && python3 -m experiments.analyse --raw results/v2 --json results/v2/analysis.json --label v2-tournament | tee results/v2/tables.md"
multipass exec tournament -- bash -c "cd search-agents-strategy-games && python3 -m experiments.report --analysis results/v2/analysis.json --out results/v2/report.md --figures results/v2/figures --run-meta results/v2/run_meta.json"
```

Everything writes under `results/v2`. **V1's data and report are untouched**, so
`results/report.md` and `results/v2/report.md` can be compared section by section.

Copy results back to Windows:

```powershell
multipass transfer tournament:/home/ubuntu/search-agents-strategy-games/results/v2/report.md .
multipass transfer tournament:/home/ubuntu/search-agents-strategy-games/results/v2/games.csv .
multipass transfer tournament:/home/ubuntu/search-agents-strategy-games/results/v2/moves.csv .
```

Sanity checks worth running on the finished data — expect **2700 games, 0 dupes, 0
errors, versions `{'v2'}`**:

```powershell
multipass exec tournament -- bash -c "cd search-agents-strategy-games && python3 -c \"
import csv, collections
G = list(csv.DictReader(open('results/v2/games.csv')))
M = [(r['game_id'], r['ply']) for r in csv.DictReader(open('results/v2/moves.csv'))]
t = collections.Counter(r['tag'] for r in csv.DictReader(open('results/v2/moves.csv')))
print('games', len(G), 'expect 2700')
print('dupes', len(M) - len(set(M)), 'expect 0')
print('illegal', t.get('illegal_move', 0), 'agent_error', t.get('agent_error', 0), 'expect 0 0')
print('versions', {r['agent_first_version'] for r in G})\""
```

---

## Getting this file onto Windows

```powershell
multipass transfer tournament:/home/ubuntu/search-agents-strategy-games/LAUNCH.md .
multipass transfer tournament:/home/ubuntu/search-agents-strategy-games/RESUME.md .
```

Or read it in place at any time:

```powershell
multipass exec tournament -- cat /home/ubuntu/search-agents-strategy-games/LAUNCH.md
```
