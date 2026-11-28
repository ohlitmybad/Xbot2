"""Local dry run of the Index bot: no Buffer, no ImgBB.

    python run_local.py --runs 5 --out local_output/batch
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ["XBOT_LOCAL"] = "1"
os.environ.setdefault("DATAMB_EMAIL", "tombolivier@gmail.com")
os.environ.setdefault("DATAMB_PASSWORD", "mbpassword1")

_HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(_HERE)
sys.path.insert(0, _HERE)

import test_twi as bot  # noqa: E402

bot.schedule_twitter_post_via_buffer = lambda *a, **k: None


def next_prefix(out_dir: str) -> tuple[int, str]:
    n = 1
    while True:
        prefix = f"{n:04d}"
        if not any(Path(out_dir).glob(f"{prefix}_*")):
            return n, prefix
        n += 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    out_dir = args.out or os.path.join(_HERE, "local_output", f"batch_{datetime.now():%Y%m%d_%H%M%S}")
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(_HERE, out_dir)
    os.makedirs(out_dir, exist_ok=True)
    all_tweets_path = os.path.join(out_dir, "all_tweets.txt")
    scratch = os.path.join(_HERE, "screenshot.png")

    saved = 0
    failures = 0
    max_fail = max(50, args.runs // 2)
    target = args.runs

    t = bot.TestUntitled()
    t.setup_method(None)
    try:
        while saved < target and failures < max_fail:
            try:
                t.test_untitled()
                _, prefix = next_prefix(out_dir)
                png = os.path.join(out_dir, f"{prefix}_index.png")
                shutil.move(scratch, png)
                tweet = t._buffer_post_text
                alt = t._buffer_alt_text
                reply = t._buffer_reply_text
                sel = getattr(t, "_selection", {})
                with open(os.path.join(out_dir, f"{prefix}_tweet.txt"), "w", encoding="utf-8") as fh:
                    fh.write(f"{tweet}\n\n--- ALT ---\n{alt}\n\n--- REPLY ---\n{reply}\n")
                with open(os.path.join(out_dir, f"{prefix}_selection.json"), "w", encoding="utf-8") as fh:
                    json.dump(sel, fh, indent=2, ensure_ascii=False)
                with open(all_tweets_path, "a", encoding="utf-8") as fh:
                    fh.write(f"===== {prefix} =====\n{tweet}\n\n")
                saved += 1
                print(f"\n[{saved}/{target}] saved {prefix}\n{'-' * 40}\n{tweet}\n{'-' * 40}", flush=True)
            except Exception as exc:
                failures += 1
                msg = f"{type(exc).__name__}: {exc!r}"
                if "not-found" in msg or "Could not select" in msg:
                    print(f"  skip bad metric ({failures}): {msg}", flush=True)
                else:
                    bot.unpop_metrics_queue()
                    print(f"  run failed ({failures}): {msg}", flush=True)
                try:
                    bot._quit_driver(t.driver)
                except Exception:
                    pass
                t.setup_method(None)
            finally:
                if os.path.exists(scratch):
                    try:
                        os.remove(scratch)
                    except OSError:
                        pass
            time.sleep(0.2)
    finally:
        try:
            t.teardown_method(None)
        except Exception:
            pass
        if os.path.exists(scratch):
            try:
                os.remove(scratch)
            except OSError:
                pass

    print(f"\nDone: {saved} saved, {failures} failed -> {out_dir}", flush=True)


if __name__ == "__main__":
    main()
