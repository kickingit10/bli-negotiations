#!/usr/bin/env python3
"""
BLI Negotiations Dashboard — Rate Verification Script
=====================================================
Run this BEFORE every deploy to verify data consistency across all files.

Usage:
    python verify-rates.py

Checks:
  1. data.json rate_comparison matches data.json final_rates
  2. analyzer.html MESOS/CURRENT objects match data.json
  3. performance.html FA_RATES match data.json current contract
  4. index.html hardcoded strings match data.json
  5. cheatsheet.html hardcoded strings match data.json
  6. Counter-offer math is correct
  7. Volume stats are consistent across files

Exit codes:
    0 = all checks passed
    1 = mismatches found
"""

import json, re, sys, os

PASS = 0
WARN = 0
FAIL = 0

def check(desc, actual, expected, tolerance=0.001):
    global PASS, WARN, FAIL
    if isinstance(actual, str) and isinstance(expected, str):
        ok = actual == expected
    elif isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        ok = abs(actual - expected) < tolerance
    else:
        ok = str(actual) == str(expected)

    if ok:
        PASS += 1
        return True
    else:
        FAIL += 1
        print(f"  FAIL: {desc}")
        print(f"        Expected: {expected}")
        print(f"        Got:      {actual}")
        return False

def warn(desc, msg):
    global WARN
    WARN += 1
    print(f"  WARN: {desc} — {msg}")

def extract_js_object(text, var_name):
    """Extract a JS object literal assigned to a variable."""
    pattern = rf'(?:const|let|var)\s+{var_name}\s*=\s*\{{([^;]+?)\}};'
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return {}
    raw = '{' + m.group(1) + '}'
    raw = re.sub(r'(\w+)\s*:', r'"\1":', raw)
    raw = re.sub(r"'([^']*)'", r'"\1"', raw)
    try:
        return json.loads(raw)
    except:
        return {}

def extract_meso_year(text, meso, year):
    """Extract a specific MESO year object like m2.y1:{...}"""
    pattern = rf'{year}:\{{([^}}]+)\}}'
    meso_pattern = rf'{meso}:\{{[^}}]*name:[^,]+,color:[^,]+,\s*' + rf'(y1:\{{[^}}]+\}}.*?y3:\{{[^}}]+\}})'
    m = re.search(meso_pattern, text, re.DOTALL)
    if not m:
        return {}
    meso_block = m.group(1)
    ym = re.search(rf'{year}:\{{([^}}]+)\}}', meso_block)
    if not ym:
        return {}
    raw = '{' + ym.group(1) + '}'
    raw = re.sub(r'(\w+)\s*:', r'"\1":', raw)
    try:
        return json.loads(raw)
    except:
        return {}

def find_hardcoded(text, pattern):
    """Find a hardcoded dollar value in narrative text."""
    m = re.search(pattern, text)
    return m.group(1) if m else None

# ── Load all files ──
script_dir = os.path.dirname(os.path.abspath(__file__))
def load(name):
    with open(os.path.join(script_dir, name)) as f:
        return f.read()

print("=" * 60)
print("BLI Negotiations Dashboard — Rate Verification")
print("=" * 60)

D = json.loads(load("data.json"))
analyzer = load("analyzer.html")
index_html = load("index.html")
perf = load("performance.html")
cheat = load("cheatsheet.html")

rc = {r["label"]: r for r in D["rate_comparison"]}
fr = D["current_contract"]["final_rates"]
vs = D["volume_stats"]

# ══════════════════════════════════════════════════════════════
print("\n1. data.json internal consistency (final_rates vs rate_comparison)")
print("-" * 60)

check("Service Charge", rc["Service Charge (weekly)"]["current"], fr["service_charge"])
check("Stop Charge", rc["Stop Charge"]["current"], fr["stop_charge"])
check("Surge Stop", rc["Surge Stop"]["current"], fr["surge_stop"])
check("Fuel Surcharge", rc["Fuel Surcharge"]["current"], fr["fuel_surcharge"])
check("Package Charge", rc["Package Charge"]["current"], fr["package_charge"])
check("LP Mix Charge", rc["LP Mix Charge"]["current"], fr["lp_mix_charge"])
check("E-Com Stop", rc["E-Com Stop"]["current"], fr["ecom_stop"])
check("E-Com Package", rc["E-Com Package"]["current"], fr["ecom_package"])
check("Apparel", rc["Apparel (weekly)"]["current"], fr["apparel"])
check("Vehicle Brand", rc["Vehicle Brand (per vehicle/wk)"]["current"], fr["vehicle_brand"])
check("Early Pull", rc["Early Pull"]["current"], fr["early_pull"])

# ══════════════════════════════════════════════════════════════
print("\n2. analyzer.html CURRENT object vs data.json")
print("-" * 60)

cur = extract_js_object(analyzer, "CURRENT")
if cur:
    check("CURRENT.service", cur.get("service"), fr["service_charge"])
    check("CURRENT.stop", cur.get("stop"), fr["stop_charge"])
    check("CURRENT.surge", cur.get("surge"), fr["surge_stop"])
    check("CURRENT.fuel", cur.get("fuel"), fr["fuel_surcharge"])
    check("CURRENT.package", cur.get("package"), fr["package_charge"])
    check("CURRENT.lp_mix", cur.get("lp_mix"), fr["lp_mix_charge"])
    check("CURRENT.ecom_stop", cur.get("ecom_stop"), fr["ecom_stop"])
    check("CURRENT.ecom_pkg", cur.get("ecom_pkg"), fr["ecom_package"])
else:
    warn("CURRENT object", "Could not parse from analyzer.html")

# ══════════════════════════════════════════════════════════════
print("\n3. analyzer.html MESO objects vs data.json rate_comparison")
print("-" * 60)

rate_map = {
    "service": "Service Charge (weekly)",
    "stop": "Stop Charge",
    "fuel": "Fuel Surcharge",
    "package": "Package Charge",
    "lp_mix": "LP Mix Charge",
    "ecom_stop": "E-Com Stop",
    "ecom_pkg": "E-Com Package",
}

for mi, mname in [("m1", "meso_1"), ("m2", "meso_2"), ("m3", "meso_3")]:
    y1 = extract_meso_year(analyzer, mi, "y1")
    if y1:
        for js_key, rc_label in rate_map.items():
            if js_key in y1 and rc_label in rc:
                check(f"{mi.upper()}.y1.{js_key}", y1[js_key], rc[rc_label][mname])
    else:
        warn(f"MESO {mi} Y1", "Could not parse from analyzer.html")

# ══════════════════════════════════════════════════════════════
print("\n4. performance.html FA_RATES vs data.json current contract")
print("-" * 60)

fa = extract_js_object(perf, "FA_RATES")
if fa:
    check("FA_RATES.service", fa.get("service"), fr["service_charge"])
    check("FA_RATES.stop", fa.get("stop"), fr["stop_charge"])
    check("FA_RATES.fuel", fa.get("fuel"), fr["fuel_surcharge"])
    check("FA_RATES.package", fa.get("package"), fr["package_charge"])
    check("FA_RATES.lp_mix", fa.get("lp_mix"), fr["lp_mix_charge"])
    check("FA_RATES.ecom_stop", fa.get("ecom_stop"), fr["ecom_stop"])
    check("FA_RATES.ecom_pkg", fa.get("ecom_pkg"), fr["ecom_package"])
else:
    warn("FA_RATES", "Could not parse from performance.html")

# ══════════════════════════════════════════════════════════════
print("\n5. index.html hardcoded strings vs data.json")
print("-" * 60)

# Counter-offer table values
m_stop = re.search(r"meso2:\s*['\"]?\$(\d+\.\d+)/stop['\"]?", index_html)
if m_stop:
    check("Counter-offer Stop Charge", float(m_stop.group(1)), rc["Stop Charge"]["meso_2"])

m_fuel = re.search(r"lever:\s*['\"]Fuel Surcharge['\"].*?meso2:\s*['\"]?\$(\d+\.\d+)/stop['\"]?", index_html, re.DOTALL)
if m_fuel:
    check("Counter-offer Fuel Surcharge", float(m_fuel.group(1)), rc["Fuel Surcharge"]["meso_2"])

m_pkg = re.search(r"lever:\s*['\"]Package Charge['\"].*?meso2:\s*['\"]?\$(\d+\.\d+)/pkg['\"]?", index_html, re.DOTALL)
if m_pkg:
    check("Counter-offer Package Charge", float(m_pkg.group(1)), rc["Package Charge"]["meso_2"])

m_ecom = re.search(r"lever:\s*['\"]E-Com Stop['\"].*?meso2:\s*['\"]?\$(\d+\.\d+)/stop['\"]?", index_html, re.DOTALL)
if m_ecom:
    check("Counter-offer E-Com Stop", float(m_ecom.group(1)), rc["E-Com Stop"]["meso_2"])

# Volume stats in narrative
m_stops = re.search(r'([\d,]+)\s*/week.*?stable volumes', index_html)
if m_stops:
    check("Narrative: delivery stops/wk", int(m_stops.group(1).replace(',', '')), vs["avg_del_stops"])

m_ecom_vol = re.search(r'e-commerce stops average ([\d,]+)/week', index_html)
if m_ecom_vol:
    check("Narrative: ecom stops/wk", int(m_ecom_vol.group(1).replace(',', '')), vs["avg_ecom_stops"])

# ══════════════════════════════════════════════════════════════
print("\n6. cheatsheet.html hardcoded strings vs data.json")
print("-" * 60)

m_cheat_ecom = re.search(r'E-Com Stop Rate.*?\$(\d+\.\d+)', cheat)
if m_cheat_ecom:
    check("Cheatsheet E-Com Stop", float(m_cheat_ecom.group(1)), rc["E-Com Stop"]["meso_2"])

m_cheat_fuel = re.search(r'Fuel Surcharge.*?\$(\d+\.\d+)', cheat)
if m_cheat_fuel:
    check("Cheatsheet Fuel Surcharge", float(m_cheat_fuel.group(1)), rc["Fuel Surcharge"]["meso_2"])

# ══════════════════════════════════════════════════════════════
print("\n7. Counter-offer math verification")
print("-" * 60)

# Stop: $0.10 increase × 1804 stops × 52 weeks
stop_impact = 0.10 * vs["avg_del_stops"] * 52
check("Stop $0.10 increase impact (~$9,400)", round(stop_impact / 100) * 100, 9400, tolerance=200)

# Package: $0.02 increase × 8039 pkgs × 52 weeks
pkg_impact = 0.02 * vs["avg_del_pkgs"] * 52
check("Package $0.02 increase impact (~$8,360)", round(pkg_impact), 8361, tolerance=50)

# E-Com: $0.13 increase × 5836 stops × 52 weeks
ecom_impact = 0.13 * vs["avg_ecom_stops"] * 52
check("E-Com $0.13 increase impact (~$39,400)", round(ecom_impact / 100) * 100, 39500, tolerance=200)

# Service charge drop: (10312 - 9360) × 52
svc_drop = (fr["service_charge"] - rc["Service Charge (weekly)"]["meso_2"]) * 52
check("Service drop impact (~$49,500)", round(svc_drop / 100) * 100, 49500, tolerance=200)

# ══════════════════════════════════════════════════════════════
print("\n8. Volume stats consistency (data.json vs analyzer.html)")
print("-" * 60)

actual_vol = re.search(r'(?<![a-z_])ec_stops_wk:\s*(\d+)', analyzer)
if actual_vol:
    check("ACTUAL_VOL.ec_stops_wk", int(actual_vol.group(1)), vs["avg_ecom_stops"])

actual_pkgs = re.search(r'(?<![a-z_])ec_pkgs_wk:\s*(\d+)', analyzer)
if actual_pkgs:
    check("ACTUAL_VOL.ec_pkgs_wk", int(actual_pkgs.group(1)), vs["avg_ecom_pkgs"])

actual_net = re.search(r'total_net:\s*([\d.]+)', analyzer)
if actual_net:
    check("ACTUAL_VOL.total_net", float(actual_net.group(1)), D["current_contract"]["totals"]["net"])

# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print(f"RESULTS: {PASS} passed, {WARN} warnings, {FAIL} failures")
print("=" * 60)

if FAIL > 0:
    print("\n*** MISMATCHES FOUND — DO NOT DEPLOY UNTIL FIXED ***")
    sys.exit(1)
elif WARN > 0:
    print("\n*** WARNINGS — Review before deploying ***")
    sys.exit(0)
else:
    print("\n✓ All checks passed — safe to deploy")
    sys.exit(0)
