"""측정 래퍼: 자식 프로세스를 띄워 최대 RSS(프로세스 트리 합)와 벽시계 시간을 잰다.
자식은 마지막에 'RESULT {json}' 한 줄을 출력한다. 결과는 results/bench.jsonl에 한 줄씩 추가한다.
사용: python bench_run.py <라벨> <python.exe> <script.py> [args...]
"""
import json, os, subprocess, sys, time
import psutil

HERE = os.path.dirname(os.path.abspath(__file__))


def tree_rss(p):
    try:
        procs = [p] + p.children(recursive=True)
        return sum(x.memory_info().rss for x in procs if x.is_running())
    except psutil.Error:
        return 0


def main(label, *cmd):
    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace", cwd=HERE)
    ps = psutil.Process(proc.pid)
    peak, lines = 0, []
    import threading
    def reader():
        for ln in proc.stdout:
            lines.append(ln)
    th = threading.Thread(target=reader, daemon=True); th.start()
    while proc.poll() is None:
        peak = max(peak, tree_rss(ps))
        time.sleep(0.05)
    th.join(5)
    wall = time.perf_counter() - t0
    res = next((json.loads(l[7:]) for l in reversed(lines) if l.startswith("RESULT ")), None)
    row = {"label": label, "exit": proc.returncode, "wall_s": round(wall, 2),
           "peak_rss_mb": round(peak / 2**20), "result": res, "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", "bench.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(os.path.join(HERE, "results", f"log_{label}.txt"), "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(json.dumps(row, ensure_ascii=False, indent=1))
    # 남은 자식 프로세스 확인(작업 종료 규칙)
    left = [c.pid for c in psutil.Process().children(recursive=True)]
    print("leftover_children:", left)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
