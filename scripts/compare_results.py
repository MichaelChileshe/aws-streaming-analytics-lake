#!/usr/bin/env python3
"""Do two query results say the same thing? Compares two CSVs from athena_run.py row by row.
Numbers may differ by 0.05 (an average summed in a different order); text must match exactly.

  python3 scripts/compare_results.py build/results/athena-q1-json.csv build/results/athena-q1-parquet.csv
"""
import csv
import sys

from kit_aws import write_result


def same(a, b):
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) <= 0.05
    except ValueError:
        return False


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    left, right = (list(csv.reader(open(p))) for p in sys.argv[1:])
    diffs = []
    if left[0] != right[0]:
        diffs.append(f"columns differ: {left[0]} vs {right[0]}")
    if len(left) != len(right):
        diffs.append(f"row counts differ: {len(left) - 1} vs {len(right) - 1}")
    for i, (a, b) in enumerate(zip(left[1:], right[1:]), 1):
        if len(a) != len(b) or not all(same(x, y) for x, y in zip(a, b)):
            diffs.append(f"row {i}: {a} vs {b}")
    name = "compare-" + "-vs-".join(p.rsplit("/", 1)[-1].replace("athena-", "").replace(".csv", "") for p in sys.argv[1:])
    result = {"left": sys.argv[1], "right": sys.argv[2], "rows": len(left) - 1, "identical": not diffs,
              "differences": diffs[:20]}
    write_result(name, result)
    if diffs:
        print("\n".join(diffs[:20]))
        print(f"RESULT compare: DIFFERENT ({len(diffs)} differences)")
        return 1
    print(f"RESULT compare: identical, {len(left) - 1} rows x {len(left[0])} columns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
