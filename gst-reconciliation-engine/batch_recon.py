import requests, json, time

BASE = "http://localhost:8001/api/v1/reconciliation"

# Get all GSTINs and periods
gstins = requests.get(f"{BASE}/gstins").json()["gstins"]
periods = requests.get(f"{BASE}/periods").json()["periods"]

print(f"GSTINs: {len(gstins)}, Periods: {len(periods)}")

# Run across more GSTINs
test_gstins = gstins[:30]
test_periods = ["042024", "082024", "112024", "022025", "032025"]

print(f"Running {len(test_gstins)} GSTINs x {len(test_periods)} periods = {len(test_gstins)*len(test_periods)} jobs...")

total_mismatches = 0
success = 0
errors = 0

for i, gstin in enumerate(test_gstins):
    for period in test_periods:
        try:
            resp = requests.post(
                f"{BASE}/run?gstin={gstin}&return_period={period}",
                timeout=120
            )
            if resp.status_code == 200:
                data = resp.json()
                mm_count = data.get("total_mismatches", 0)
                total_mismatches += mm_count
                success += 1
                if mm_count > 0:
                    print(f"  {gstin} | {period} => {mm_count} mismatches")
            else:
                errors += 1
        except requests.exceptions.Timeout:
            errors += 1
            print(f"  {gstin} | {period} => TIMEOUT")
        except Exception as e:
            errors += 1

    if (i+1) % 10 == 0:
        print(f"  Progress: {(i+1)*len(test_periods)}/{len(test_gstins)*len(test_periods)} done, {total_mismatches} total mismatches")

print(f"\nDone! {success} success, {errors} errors, {total_mismatches} total mismatches")
