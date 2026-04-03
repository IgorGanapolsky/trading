#!/usr/bin/env bash
# CI test runner with watchdog timeouts and deterministic artifacts.

set -euo pipefail

REPORT_DIR="${REPORT_DIR:-artifacts/test-reports}"
PYTEST_TIMEOUT_SECONDS="${PYTEST_TIMEOUT_SECONDS:-300}"
CORE_TIMEOUT_MINUTES="${CORE_TIMEOUT_MINUTES:-28}"
INTEGRATION_TIMEOUT_MINUTES="${INTEGRATION_TIMEOUT_MINUTES:-12}"
COV_FAIL_UNDER="${COV_FAIL_UNDER:-15}"
HEARTBEAT_SECONDS="${HEARTBEAT_SECONDS:-60}"
PYTHON_BIN="${PYTHON_BIN-}"
COV_TARGET="${COV_TARGET:-src}"
CORE_TARGETS="${CORE_TARGETS:-tests --ignore=tests/integration}"
INTEGRATION_TARGETS="${INTEGRATION_TARGETS:-tests/integration}"
CRITICAL_COVERAGE_SCRIPT="${CRITICAL_COVERAGE_SCRIPT:-scripts/ci/check_critical_coverage.py}"

mkdir -p "${REPORT_DIR}"

log() {
	printf '[ci-tests] %s\n' "$1"
}

resolve_timeout_cmd() {
	if command -v timeout >/dev/null 2>&1; then
		echo "timeout"
		return 0
	fi
	if command -v gtimeout >/dev/null 2>&1; then
		echo "gtimeout"
		return 0
	fi
	echo ""
	return 0
}

resolve_python_bin() {
	local -a candidates=()
	if [[ -n ${PYTHON_BIN} ]]; then
		candidates+=("${PYTHON_BIN}")
	fi
	candidates+=("./.venv/bin/python" ".venv/bin/python" "python3.11" "python3" "python")

	local candidate
	for candidate in "${candidates[@]}"; do
		if ! command -v "${candidate}" >/dev/null 2>&1; then
			continue
		fi
		if "${candidate}" - <<'PY' >/dev/null 2>&1; then
import importlib.util
import sys
required = ("pytest", "coverage")
sys.exit(0 if all(importlib.util.find_spec(mod) for mod in required) else 1)
PY
			echo "${candidate}"
			return 0
		fi
	done

	local fallback=""
	for candidate in "${candidates[@]}"; do
		if command -v "${candidate}" >/dev/null 2>&1; then
			fallback="${candidate}"
			break
		fi
	done
	if [[ -n ${fallback} ]]; then
		echo "${fallback}"
		return 0
	fi
	log "no python interpreter with pytest/coverage found"
	exit 1
}

resolve_pytest_timeout_args() {
	local python_bin="$1"
	if "${python_bin}" - <<'PY' >/dev/null 2>&1; then
import importlib.util
import sys
sys.exit(0 if importlib.util.find_spec("pytest_timeout") else 1)
PY
		echo "--timeout=${PYTEST_TIMEOUT_SECONDS} --timeout-method=thread"
	else
		echo ""
	fi
}

run_phase() {
	local phase="$1"
	local max_minutes="$2"
	shift 2

	local timeout_cmd
	timeout_cmd="$(resolve_timeout_cmd)"
	local python_bin
	python_bin="$(resolve_python_bin)"
	local timeout_args
	timeout_args="$(resolve_pytest_timeout_args "${python_bin}")"
	local -a timeout_args_arr=()
	if [[ -n ${timeout_args} ]]; then
		read -r -a timeout_args_arr <<<"${timeout_args}"
	fi
	local log_file="${REPORT_DIR}/${phase}.log"
	local junit_file="${REPORT_DIR}/junit-${phase}.xml"
	local rc_file="${REPORT_DIR}/.${phase}.rc"
	local -a pytest_targets=("$@")

	rm -f "${rc_file}"

	log "starting phase=${phase} timeout=${max_minutes}m"
	set +e
	(
		if [[ -n ${timeout_cmd} ]]; then
			"${timeout_cmd}" --signal=TERM --kill-after=120 "$((max_minutes * 60))" \
				"${python_bin}" -m pytest \
				-v \
				--tb=long \
				--durations=25 \
				"${timeout_args_arr[@]}" \
				--cov="${COV_TARGET}" \
				--cov-append \
				--cov-report= \
				--junitxml="${junit_file}" \
				"${pytest_targets[@]}"
			echo $? >"${rc_file}"
		else
			log "timeout command not available; running phase without outer watchdog"
			"${python_bin}" -m pytest \
				-v \
				--tb=long \
				--durations=25 \
				"${timeout_args_arr[@]}" \
				--cov="${COV_TARGET}" \
				--cov-append \
				--cov-report= \
				--junitxml="${junit_file}" \
				"${pytest_targets[@]}"
			echo $? >"${rc_file}"
		fi
	) 2>&1 | tee "${log_file}" &
	local pipeline_pid=$!
	local started_epoch
	started_epoch="$(date +%s)"

	while kill -0 "${pipeline_pid}" 2>/dev/null; do
		sleep "${HEARTBEAT_SECONDS}"
		if kill -0 "${pipeline_pid}" 2>/dev/null; then
			local now_epoch
			now_epoch="$(date +%s)"
			local elapsed
			elapsed=$((now_epoch - started_epoch))
			log "heartbeat phase=${phase} elapsed=${elapsed}s"
		fi
	done

	wait "${pipeline_pid}"
	local pipeline_rc=$?
	local rc="${pipeline_rc}"
	if [[ -f ${rc_file} ]]; then
		rc="$(<"${rc_file}")"
		rm -f "${rc_file}"
	fi
	set -e

	if [[ ${rc} -eq 124 ]]; then
		log "phase=${phase} timed out"
		tail -n 200 "${log_file}" || true
		return 124
	fi
	if [[ ${rc} -ne 0 ]]; then
		log "phase=${phase} failed with rc=${rc}"
		tail -n 200 "${log_file}" || true
		return "${rc}"
	fi

	log "phase=${phase} passed"
}

rm -f .coverage coverage.xml

if [[ ! -d tests ]]; then
	log "tests directory missing"
	exit 1
fi

read -r -a core_targets <<<"${CORE_TARGETS}"
run_phase "core" "${CORE_TIMEOUT_MINUTES}" "${core_targets[@]}"

if find tests/integration -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then
	read -r -a integration_targets <<<"${INTEGRATION_TARGETS}"
	run_phase "integration" "${INTEGRATION_TIMEOUT_MINUTES}" "${integration_targets[@]}"
else
	log "integration phase skipped: no tests/integration test files"
fi

python_bin="$(resolve_python_bin)"
"${python_bin}" -m coverage xml -o coverage.xml
"${python_bin}" -m coverage report --fail-under="${COV_FAIL_UNDER}" | tee "${REPORT_DIR}/coverage.txt"

# Per-file coverage enforcement for critical trading files
log "checking critical file coverage minimums..."
if [[ -f ${CRITICAL_COVERAGE_SCRIPT} ]]; then
	"${python_bin}" "${CRITICAL_COVERAGE_SCRIPT}" coverage.xml || {
		log "CRITICAL FILE COVERAGE CHECK FAILED"
		exit 1
	}
else
	log "critical coverage script missing; skipping per-file enforcement"
fi

log "all phases complete"
