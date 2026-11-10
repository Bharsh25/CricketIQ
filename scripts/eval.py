import json, re, time
from app.agent.graph import ask

golden = json.load(open("tests/golden.json"))
RUN = int(time.time())          # fresh thread IDs on every run

def has_number(answer: str, expected: float) -> bool:
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", answer.replace(",", ""))]
    return any(abs(n - expected) <= max(0.01, abs(expected) * 0.005) for n in nums)

tool_ok = ans_ok = passed = errors = 0
lat, rows = [], []
for i, g in enumerate(golden):
    t0 = time.time()
    try:
        ans, used = ask(g["q"], thread_id=f"eval-{RUN}-{i}")
    except Exception as e:
        errors += 1
        print("ERROR |", g["q"], "|", str(e)[:150])
        rows.append({**g, "error": str(e)[:200]})
        time.sleep(3)
        continue
    dt = time.time() - t0
    lat.append(dt)
    t_ok = any(u["name"] == g["tool"] for u in used)
    a_ok = has_number(ans, g["expected"])
    tool_ok += t_ok
    ans_ok += a_ok
    passed += t_ok and a_ok
    status = "PASS" if t_ok and a_ok else "FAIL"
    print(status, "|", g["q"])
    if status == "FAIL":
        print("   tool_ok:", t_ok, "| answer_ok:", a_ok,
              "| tools:", [u["name"] for u in used], "| got:", ans[:100].replace("\n", " "))
    rows.append({"q": g["q"], "tool_ok": t_ok, "answer_ok": a_ok, "tools": used,
                 "expected": g["expected"], "answer": ans[:200], "latency_s": round(dt, 1)})
    time.sleep(2)                # stay under the free-tier rate limit

n = len(golden)
print(f"\nTool-choice accuracy : {tool_ok}/{n}")
print(f"Answer accuracy      : {ans_ok}/{n}")
print(f"Overall pass rate    : {passed}/{n}")
print(f"Errors               : {errors}")
if lat:
    print(f"Avg latency          : {sum(lat)/len(lat):.1f}s")
json.dump(rows, open("tests/eval_results.json", "w"), indent=2)