"""Analyse MindAssist revision sessions against cue ground truth.

Ground truth comes from cues.csv (what the participant was told to do and
when), never from the headset's blink detector. Every decision path is
recomputed from events.csv, so all paths are compared on the same blinks:

  rule                 threshold + 1 s pairing, no gate
  rule+gate(deployed)  the gate as originally shipped, at 0.60
  rule+gate(corrected) the corrected gate, at 0.60 and stricter settings
  rule+model veto      events the model calls "no blink" (p >= 0.5) are dropped
  rule+gate+veto       corrected gate and model veto together

Per path: hit rate for single and double cues, wrong-type rate, false
activations under REST and each confounder, unprompted actions per minute,
with Wilson 95% intervals and paired McNemar tests against the rule.

Latency (from the live run): blink packet -> serial write, serial write ->
ESP32 acknowledgment, cue onset -> acknowledgment, and the single-blink
dispatch delay of the original main.py's packet-driven loop, reconstructed from the packets.

usage: python analyze_session.py <session_dir> [<session_dir> ...] --out report_dir
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest

INTERVAL, GATE = 1.0, 0.60
WINDOW_START, WINDOW_END_AFTER_OFFSET = 0.10, 1.0   # a blink counts for a trial if it starts in this window
CONFOUNDERS = ["FROWN", "EYEBROWS", "LOOK_LEFT", "LOOK_RIGHT", "JAW"]
KIND_OF = {"SINGLE": "single", "DOOR": "single", "DOUBLE": "double", "WINDOW": "double"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def fmt(k, n):
    p, lo, hi = wilson(k, n)
    return "n/a" if n == 0 else f"{k}/{n} = {100*p:.0f}% [{100*lo:.0f}-{100*hi:.0f}]"


# ------------------------------------------------------------ decision replay
def replay(ev: pd.DataFrame, accept, kind_from_model=False, packet_times=None):
    """Re-run main.py's pairing logic on logged events. Returns a list of
    actions {t_blink, t_dispatch, kind, ids}. accept(row) -> bool is the gate."""
    actions, pending = [], None

    def dispatch_single(p):
        t_d = p["t"] + INTERVAL
        if packet_times is not None:  # original main.py: only checked when the next packet arrives
            later = packet_times[packet_times > t_d]
            t_d = float(later[0]) if len(later) else t_d
        return t_d

    for _, r in ev[ev.rule_pass == 1].sort_values("t").iterrows():
        if pending is not None and r.t - pending["t"] > INTERVAL:
            actions.append({"t_blink": pending["t"], "t_dispatch": dispatch_single(pending), "kind": "single",
                            "ids": [pending["id"]], "p_double": pending["p_double"], "p_single": pending["p_single"]})
            pending = None
        if not accept(r):
            continue
        rec = {"t": r.t, "id": int(r.event_id), "p_single": r.p_single, "p_double": r.p_double}
        if pending is not None and r.t - pending["t"] <= INTERVAL:
            actions.append({"t_blink": pending["t"], "t_dispatch": r.t, "kind": "double",
                            "ids": [pending["id"], rec["id"]], "p_double": r.p_double, "p_single": r.p_single})
            pending = None
        else:
            pending = rec
    if pending is not None:
        actions.append({"t_blink": pending["t"], "t_dispatch": dispatch_single(pending), "kind": "single",
                        "ids": [pending["id"]], "p_double": pending["p_double"], "p_single": pending["p_single"]})
    if kind_from_model:
        for a in actions:
            if not (np.isnan(a["p_double"]) or np.isnan(a["p_single"])):
                a["kind"] = "double" if a["p_double"] > a["p_single"] else "single"
    return actions


def paths(ev):
    has_model = ev.p_noblink.notna().any()
    out = {
        "rule (no gate)": dict(accept=lambda r: True),
        "rule + deployed gate 0.60": dict(accept=lambda r: r.conf_deployed >= GATE),
        "rule + corrected gate 0.60": dict(accept=lambda r: r.conf_corrected >= GATE),
        "rule + corrected gate 0.70": dict(accept=lambda r: r.conf_corrected >= 0.70),
        "rule + corrected gate 0.80": dict(accept=lambda r: r.conf_corrected >= 0.80),
    }
    if has_model:
        out["rule + model veto"] = dict(accept=lambda r: not (r.p_noblink >= 0.5))
        out["rule + corrected gate + model veto"] = dict(
            accept=lambda r: r.conf_corrected >= GATE and not (r.p_noblink >= 0.5))
        out["rule + model veto, model picks type"] = dict(
            accept=lambda r: not (r.p_noblink >= 0.5), kind_from_model=True)
    return out


# ------------------------------------------------------------------- scoring
def score(cues: pd.DataFrame, actions: list[dict], duration_min: float):
    acts = sorted(actions, key=lambda a: a["t_blink"])
    used = set()
    rows = []
    for _, c in cues.iterrows():
        lo, hi = c.t_onset + WINDOW_START, c.t_offset + WINDOW_END_AFTER_OFFSET
        inside = [i for i, a in enumerate(acts) if lo <= a["t_blink"] <= hi]
        used.update(inside)
        exp = KIND_OF.get(c.cue, "none")
        if exp == "none":
            outcome = "false_activation" if inside else "correct_reject"
        elif not inside:
            outcome = "miss"
        else:
            outcome = "correct" if acts[inside[0]]["kind"] == exp else "wrong_type"
        rows.append({"trial": c.trial, "cue": c.cue, "expected": exp, "outcome": outcome,
                     "extra_actions": max(0, len(inside) - 1)})
    df = pd.DataFrame(rows)
    unprompted = len(acts) - len(used)
    return df, unprompted, unprompted / duration_min if duration_min else np.nan


def summarise(df, unprompted, per_min):
    s = {}
    for kind in ("single", "double"):
        sub = df[df.expected == kind]
        s[f"{kind}_hit"] = (int((sub.outcome == "correct").sum()), len(sub))
        s[f"{kind}_wrong_type"] = (int((sub.outcome == "wrong_type").sum()), len(sub))
        s[f"{kind}_miss"] = (int((sub.outcome == "miss").sum()), len(sub))
    rest = df[df.cue == "REST"]
    s["rest_false_activation"] = (int((rest.outcome == "false_activation").sum()), len(rest))
    conf = df[df.cue.isin(CONFOUNDERS)]
    s["confounder_false_activation"] = (int((conf.outcome == "false_activation").sum()), len(conf))
    for c in CONFOUNDERS:
        sub = df[df.cue == c]
        s[f"fa_{c}"] = (int((sub.outcome == "false_activation").sum()), len(sub))
    ok = df.outcome.isin(["correct", "correct_reject"])
    s["trial_accuracy"] = (int(ok.sum()), len(df))
    s["unprompted_actions"] = unprompted
    s["unprompted_per_min"] = per_min
    return s


def mcnemar(a_ok, b_ok):
    n01 = int(np.sum(a_ok & ~b_ok)); n10 = int(np.sum(~a_ok & b_ok))
    return n01, n10, (binomtest(min(n01, n10), n01 + n10, 0.5).pvalue if n01 + n10 else 1.0)


def describe(x):
    x = np.asarray([v for v in x if np.isfinite(v)])
    if not len(x):
        return "n/a"
    return (f"median {np.median(x)*1000:.0f} ms, IQR {np.percentile(x,25)*1000:.0f}-{np.percentile(x,75)*1000:.0f}, "
            f"p95 {np.percentile(x,95)*1000:.0f}, n={len(x)}")


# ------------------------------------------------------------------ sessions
def load(d: Path):
    s = {k: pd.read_csv(d / f"{k}.csv") for k in ("cues", "events", "packets", "actions", "acks")}
    s["meta"] = json.loads((d / "meta.json").read_text())
    s["dir"] = d
    return s


def latency(s):
    acts, acks, ev, cues = s["actions"], s["acks"], s["events"], s["cues"]
    acks = acks[acks.line.astype(str).str.startswith("ACK") & ~acks.line.astype(str).str.contains("BLOCKED")].copy()
    acks["target"] = acks.line.str.split(":").str[1]
    out = {"write_after_last_blink_double": [], "write_after_blink_single": [], "ack_after_write": [],
           "ack_after_last_blink_double": [], "ack_after_cue_onset": []}
    for _, a in acts.iterrows():
        dt = a.t_serial_write - a.t_last_event
        out["write_after_last_blink_double" if a.kind == "double" else "write_after_blink_single"].append(dt)
        cand = acks[(acks.t >= a.t_serial_write) & (acks.target == a.target)]
        if len(cand):
            t_ack = float(cand.t.iloc[0])
            out["ack_after_write"].append(t_ack - a.t_serial_write)
            if a.kind == "double":
                out["ack_after_last_blink_double"].append(t_ack - a.t_last_event)
            c = cues[(cues.t_onset <= a.t_last_event) & (a.t_last_event <= cues.t_offset + WINDOW_END_AFTER_OFFSET)]
            if len(c):
                out["ack_after_cue_onset"].append(t_ack - float(c.t_onset.iloc[0]))
    # the original main.py's packet-driven single dispatch, reconstructed
    pk = s["packets"].t.values
    out["single_dispatch_mainpy_after_blink"] = [
        a["t_dispatch"] - a["t_blink"] for a in replay(ev, lambda r: True, packet_times=pk) if a["kind"] == "single"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", nargs="+")
    ap.add_argument("--out", default="report")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    sessions = [load(Path(p)) for p in a.sessions]
    md, js = ["# MindAssist revision session report", ""], {"sessions": []}
    md += ["Ground truth is the cue shown on screen, logged independently of the headset's blink detector.",
           f"A blink counts for a trial if it starts between {WINDOW_START:.2f} s after cue onset and "
           f"{WINDOW_END_AFTER_OFFSET:.1f} s after the cue disappears.", ""]

    # ---- per-path accuracy, pooled over detection sessions
    for block in ("detection", "task"):
        group = [s for s in sessions if s["meta"]["block"] == block]
        if not group:
            continue
        md += [f"## {block.capitalize()} block ({len(group)} session(s), participants: "
               f"{', '.join(sorted({s['meta']['participant'] for s in group}))})", ""]
        pooled = {}
        for s in group:
            dur = (s["cues"].t_offset.max() - s["cues"].t_fixation.min()) / 60
            for name, kw in paths(s["events"]).items():
                df, un, _ = score(s["cues"], replay(s["events"], **kw), dur)
                df["session"] = s["dir"].name
                p = pooled.setdefault(name, {"df": [], "unprompted": 0, "minutes": 0.0})
                p["df"].append(df); p["unprompted"] += un; p["minutes"] += dur
        header = ["path", "single cue -> single", "double cue -> double", "REST -> action (false)",
                  "confounder -> action (false)", "unprompted / min", "all trials correct"]
        md += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        js_block = {}
        base_ok = None
        tests = []
        for name, p in pooled.items():
            df = pd.concat(p["df"], ignore_index=True)
            sm = summarise(df, p["unprompted"], p["unprompted"] / p["minutes"])
            js_block[name] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in sm.items()}
            md.append(f"| {name} | {fmt(*sm['single_hit'])} | {fmt(*sm['double_hit'])} | "
                      f"{fmt(*sm['rest_false_activation'])} | {fmt(*sm['confounder_false_activation'])} | "
                      f"{sm['unprompted_per_min']:.2f} | {fmt(*sm['trial_accuracy'])} |")
            ok = df.outcome.isin(["correct", "correct_reject"]).values
            if base_ok is None:
                base_ok = ok
            else:
                n01, n10, p_ = mcnemar(base_ok, ok)
                tests.append(f"| {name} | {n01} | {n10} | {p_:.3g} |")
        md += ["", "Paired against the rule on the same trials (McNemar, exact):", "",
               "| path | rule right, path wrong | path right, rule wrong | p |", "|---|---|---|---|", *tests, ""]
        if block == "detection":
            df = pd.concat(pooled["rule (no gate)"]["df"])
            md += ["False activations by confounder (rule, no gate | rule + corrected gate 0.60):", ""]
            dfg = pd.concat(pooled["rule + corrected gate 0.60"]["df"])
            for c in CONFOUNDERS:
                k1 = int(((df.cue == c) & (df.outcome == "false_activation")).sum()); n1 = int((df.cue == c).sum())
                k2 = int(((dfg.cue == c) & (dfg.outcome == "false_activation")).sum())
                md.append(f"- {c}: {fmt(k1, n1)} | {fmt(k2, n1)}")
            md.append("")
        if block == "task":
            md += ["Live gate setting per task session (what actually drove the servos):", ""]
            for s in group:
                g = s["meta"]["gate"]
                dur = (s["cues"].t_offset.max() - s["cues"].t_fixation.min()) / 60
                ev = s["events"].set_index("event_id")
                live = []
                for _, r in s["actions"].iterrows():   # first blink of each live action
                    ids = [int(i) for i in str(r.event_ids).split(";") if i]
                    t_b = float(ev.loc[ids[0], "t"]) if ids and ids[0] in ev.index else float(r.t_last_event)
                    live.append({"t_blink": t_b, "kind": r.kind})
                df, un, pm = score(s["cues"], live, dur)
                sm = summarise(df, un, pm)
                md.append(f"- gate **{g}** ({s['dir'].name}): door {fmt(*sm['single_hit'])}, window "
                          f"{fmt(*sm['double_hit'])}, unprompted {pm:.2f}/min")
            md.append("")
        js[block] = js_block

    # ---- validation: offline replay must reproduce what the live run sent
    md += ["## Replay check", ""]
    gate_paths = {"off": "rule (no gate)", "deployed": "rule + deployed gate 0.60",
                  "corrected": "rule + corrected gate 0.60"}
    for s in sessions:
        kw = paths(s["events"])[gate_paths[s["meta"]["gate"]]]
        rep = {(a["kind"], a["ids"][0]) for a in replay(s["events"], **kw)}
        live = {(r.kind, int(str(r.event_ids).split(";")[0])) for _, r in s["actions"].iterrows()}
        md.append(f"- {s['dir'].name}: live actions {len(live)}, replayed {len(rep)}, identical: "
                  f"{'yes' if rep == live else 'NO - ' + str(sorted(rep ^ live)[:5])}")
    md.append("")

    # ---- latency
    md += ["## Latency (live run)", ""]
    lat = {}
    for s in sessions:
        for k, v in latency(s).items():
            lat.setdefault(k, []).extend(v)
    labels = {
        "write_after_last_blink_double": "double blink: second blink packet -> serial command",
        "ack_after_write": "serial command -> ESP32 acknowledgment",
        "ack_after_last_blink_double": "double blink: second blink packet -> ESP32 acknowledgment",
        "write_after_blink_single": "single blink: blink packet -> serial command (includes the 1 s wait)",
        "single_dispatch_mainpy_after_blink": "single blink dispatch, original main.py packet-driven loop (reconstructed)",
        "ack_after_cue_onset": "cue onset -> ESP32 acknowledgment (includes human reaction time)",
    }
    for k, lab in labels.items():
        md.append(f"- {lab}: {describe(lat.get(k, []))}")
    js["latency_s"] = {k: [float(x) for x in v] for k, v in lat.items()}
    if not any(len(v) for k, v in lat.items() if k.startswith("ack")):
        md.append("- no ESP32 acknowledgments found: was the firmware patch flashed?")

    # ---- the model's inputs as deployed
    ev = pd.concat([s["events"] for s in sessions])
    ev = ev[ev.rule_pass == 1]
    if ev.legacy_p_noblink.notna().any():
        leg = (ev.legacy_p_noblink >= 0.99).mean()
        fix = (ev.p_noblink >= 0.5).mean()
        md += ["", "## Model inputs", "",
               f"- With inputs built as the original main.py built them, the model predicted 'no blink' at p >= 0.99 on "
               f"{100*leg:.0f}% of {len(ev)} blink events.",
               f"- With inputs built as in training (carried-forward eSense and bands, session time), it predicted "
               f"'no blink' on {100*fix:.0f}%.",
               f"- Model inference time: {describe(ev.model_ms.values / 1000)}"]
    (out / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (out / "report.json").write_text(json.dumps(js, indent=2, default=float))
    print("\n".join(md))


if __name__ == "__main__":
    main()
