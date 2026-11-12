package jcode.governance

# 语法版本: OPA 1.x 默认启用 rego.v1（部分集合规则必须写 contains/if，
# `package` 等保留字不能再当字段名直接点号访问）。旧版 v0 写法在
# OPA 1.x 下直接 parse 失败 → 策略作业必红，故按 v1 语法书写。

import rego.v1

# ──────────────────────────────────────────────────────
# Policy: No Critical Vulnerabilities
# ──────────────────────────────────────────────────────
violations contains {"rule": "no-critical-vulns", "message": msg, "severity": "critical"} if {
	some vuln in input.supply_chain_scan.vulnerabilities
	vuln.severity == "critical"
	msg := sprintf("Critical vulnerability found: %s (%s)", [vuln.id, vuln["package"]])
}

# ──────────────────────────────────────────────────────
# Policy: No High Vulnerabilities (without approved exception)
# ──────────────────────────────────────────────────────
violations contains {"rule": "no-high-vulns", "message": msg, "severity": "high"} if {
	some vuln in input.supply_chain_scan.vulnerabilities
	vuln.severity == "high"
	not has_exception(vuln.id)
	msg := sprintf("High vulnerability found without exception: %s (%s)", [vuln.id, vuln["package"]])
}

has_exception(vuln_id) if {
	some exc in input.exceptions
	exc.status == "approved"
	exc.cve_id == vuln_id
}

# ──────────────────────────────────────────────────────
# Policy: No Circular Dependencies
# ──────────────────────────────────────────────────────
violations contains {"rule": "no-circular-deps", "message": msg, "severity": "high"} if {
	some cycle in input.dependencies.cycles
	msg := sprintf("Circular dependency detected: %s", [concat(" → ", cycle)])
}

# ──────────────────────────────────────────────────────
# Policy: No Version Conflicts
# ──────────────────────────────────────────────────────
violations contains {"rule": "no-version-conflicts", "message": msg, "severity": "medium"} if {
	some conflict in input.dependencies.conflicts
	msg := sprintf("Version conflict: %s has versions %s", [conflict["package"], concat(", ", conflict.versions)])
}

# ──────────────────────────────────────────────────────
# Policy: Dependency Freshness - No stale dependencies
# ──────────────────────────────────────────────────────
violations contains {"rule": "dependency-freshness", "message": msg, "severity": "medium"} if {
	some stale in input.supply_chain_freshness.stale_dependencies
	stale.days_since_update > 365
	msg := sprintf("Dependency %s is stale (last updated %d days ago)", [stale["package"], stale.days_since_update])
}

# ──────────────────────────────────────────────────────
# Policy: License Compliance
# ──────────────────────────────────────────────────────
violations contains {"rule": "license-compliance", "message": msg, "severity": "high"} if {
	some dep in input.supply_chain_compliance.license_violations
	msg := sprintf("License violation: %s uses %s (not allowed)", [dep["package"], dep.license])
}

# ──────────────────────────────────────────────────────
# Policy: SLSA Provenance Verification
# ──────────────────────────────────────────────────────
violations contains {"rule": "slsa-provenance", "message": msg, "severity": "high"} if {
	some result in input.supply_chain_verify.verification_results
	not result.verified
	msg := sprintf("SLSA provenance verification failed for %s: %s", [result["package"], result.reason])
}

# ──────────────────────────────────────────────────────
# Policy: Exception Expiration
# ──────────────────────────────────────────────────────
violations contains {"rule": "exception-expiration", "message": msg, "severity": "medium"} if {
	some exc in input.exceptions
	exc.status == "approved"
	exc.expires_at != ""
	time.now_ns() > time.parse_rfc3339_ns(exc.expires_at)
	msg := sprintf("Exception %s has expired on %s", [exc.id, exc.expires_at])
}

# ──────────────────────────────────────────────────────
# Policy: Exception Approaching Expiration (30 days)
# ──────────────────────────────────────────────────────
violations contains {"rule": "exception-expiring-soon", "message": msg, "severity": "low"} if {
	some exc in input.exceptions
	exc.status == "approved"
	exc.expires_at != ""
	time.now_ns() + 30 * 24 * 60 * 60 * 1e9 > time.parse_rfc3339_ns(exc.expires_at)
	time.now_ns() < time.parse_rfc3339_ns(exc.expires_at)
	msg := sprintf("Exception %s expires within 30 days (%s)", [exc.id, exc.expires_at])
}

# ──────────────────────────────────────────────────────
# Policy: Supply Chain Integrity - Verified Dependencies
# ──────────────────────────────────────────────────────
violations contains {"rule": "unverified-dependency", "message": msg, "severity": "medium"} if {
	some dep in input.sbom.dependencies
	not dep.verified
	msg := sprintf("Unverified dependency in SBOM: %s@%s", [dep.name, dep.version])
}

# ──────────────────────────────────────────────────────
# Policy: No Deprecated Dependencies
# ──────────────────────────────────────────────────────
violations contains {"rule": "no-deprecated-deps", "message": msg, "severity": "low"} if {
	some dep in input.supply_chain_scan.dependencies
	dep.deprecated == true
	msg := sprintf("Deprecated dependency: %s@%s - %s", [dep.name, dep.version, dep.deprecation_reason])
}
