"""Stage 1-3 tests. No network, no credentials, no AI - which is the point.

The format-variant tests are the ones that matter for adoption: Serilog writes
a different header depending on the sink's output template, and a parser that
only handles one of them is a parser that works on the demo machine and nowhere
else.
"""

from __future__ import annotations

import pytest

from engine.knowledge import load_config
from engine.parser import build_blocks, parse, parse_lines


@pytest.fixture
def topology():
    return load_config()["topology"]


# --------------------------------------------------------------------------
# Header format variants
# --------------------------------------------------------------------------

FORMATS = {
    "bare time":        "11:20:07 INF Supplier Details synced started",
    "bracketed":        "[11:20:07 INF] Supplier Details synced started",
    "full iso offset":  "2026-08-18 11:20:07.123 +05:30 [INF] Supplier Details synced started",
    "iso T with Z":     "2026-08-18T11:20:07.1234567Z INF Supplier Details synced started",
    "date space level": "2026-08-18 11:20:07.123 INF Supplier Details synced started",
    "long level name":  "11:20:07 [Information] Supplier Details synced started",
    "comma fraction":   "2026-08-18 11:20:07,123 INF Supplier Details synced started",
    "slash date":       "2026/08/18 11:20:07 INF Supplier Details synced started",
}


@pytest.mark.parametrize("label,line", list(FORMATS.items()), ids=list(FORMATS))
def test_header_formats_are_recognised(label, line):
    lines = parse_lines(line)
    assert lines[0].is_header, f"{label} was not recognised as a header"
    assert lines[0].time == "11:20:07"
    assert lines[0].level == "INF"
    assert "Supplier Details" in lines[0].message


def test_all_levels_normalise():
    text = "\n".join([
        "01:00:00 VRB verbose line",
        "01:00:01 DBG debug line",
        "01:00:02 INF info line",
        "01:00:03 WRN warn line",
        "01:00:04 ERR error line",
        "01:00:05 FTL fatal line",
        "01:00:06 [Warning] long warn",
        "01:00:07 [Error] long error",
    ])
    levels = [l.level for l in parse_lines(text) if l.is_header]
    assert levels == ["VRB", "DBG", "INF", "WRN", "ERR", "FTL", "WRN", "ERR"]


# --------------------------------------------------------------------------
# Block building: a stack trace must stay attached to its ERR line
# --------------------------------------------------------------------------

STACK = """11:21:07 ERR Failed due to an issue in method "https://gateway.suppliersync.internal/api/supplier":
System.Net.Http.HttpRequestException: An error occurred while sending the request.
 ---> System.Net.Http.HttpIOException: The response ended prematurely. (ResponseEnded)
   at System.Net.Http.HttpConnection.SendAsyncCore(HttpRequestMessage request)
   at SupplierSync.Api.FetchGalileoApi.GetAPIResponse(String url) in C:\\src\\FetchGalileoApi.cs:line 59
11:21:07 INF Email Trigger sent"""


def test_stack_trace_stays_in_one_block():
    blocks, _ = build_blocks(parse_lines(STACK))
    assert len(blocks) == 2
    err = blocks[0]
    assert err.level == "ERR"
    assert len(err.continuation) == 4
    assert "HttpIOException" in err.text
    assert "line 59" in err.text


def test_indented_trace_line_is_not_mistaken_for_a_header():
    """A trace frame carrying something time-shaped must not split the block."""
    text = (
        "11:21:07 ERR Failed\n"
        "   at Ald.Job.Run() in C:\\src\\Job.cs:line 12\n"
        "        12:34:56 this is indented noise, not a log header\n"
        "11:21:08 INF next"
    )
    blocks, _ = build_blocks(parse_lines(text))
    assert len(blocks) == 2
    assert len(blocks[0].continuation) == 2


def test_unparseable_input_warns_rather_than_crashing(topology):
    result = parse("this is not a log at all\njust some prose", topology)
    assert result.facts["has_error"] is False
    assert any("No Serilog header" in w for w in result.warnings)


def test_empty_input_is_safe(topology):
    result = parse("", topology)
    assert result.facts["has_error"] is False
    assert result.evidence == []


# --------------------------------------------------------------------------
# Evidence extraction
# --------------------------------------------------------------------------

def test_exception_chain_order_is_outermost_first(topology):
    result = parse(STACK, topology)
    assert result.facts["exception_types"] == ["HttpRequestException", "HttpIOException"]


def test_endpoint_host_is_extracted(topology):
    result = parse(STACK, topology)
    assert result.facts["endpoint_host"] == "gateway.suppliersync.internal"


@pytest.mark.parametrize("text,expected", [
    ("10:00:00 ERR x\nSystem.Net.Http.HttpRequestException: Response status code does not indicate success: 401 (Unauthorized).", 401),
    ("10:00:00 ERR x\nSystem.Net.Http.HttpRequestException: Response status code does not indicate success: 503 (Service Unavailable).", 503),
    ("10:00:00 ERR x\nRemote returned 502 Bad Gateway", 502),
    ("10:00:00 ERR x\nStatus code: 403", 403),
])
def test_http_status_extraction(text, expected, topology):
    assert parse(text, topology).facts["http_status"] == expected


def test_status_from_a_success_line_is_not_treated_as_an_error_status(topology):
    """A 200 in an INF line must not become the failure's status."""
    text = (
        "10:00:00 INF Total Records Fetched for Supplier Details: 5\n"
        "10:00:00 INF Supplier Details synced started\n"
        "10:00:01 INF Supplier Details synced completed. Status: 200 OK"
    )
    assert parse(text, topology).facts["http_status"] is None


def test_service_state_is_attributed_to_the_service_source(topology):
    text = "02:00:05 WRN Service SupplierSyncWorker is Stopped"
    result = parse(text, topology)
    assert result.facts["service_state"] == "Stopped"
    assert any(e.source == "windows_service" for e in result.evidence)


# --------------------------------------------------------------------------
# Stage 3: derived facts. This is where the root cause actually comes from.
# --------------------------------------------------------------------------

PRODUCTION_CASE = """2026-08-18 11:03:05.771 +05:30 [INF] Total Records Fetched for Supplier Addresses: 39
2026-08-18 11:03:05.772 +05:30 [INF] Supplier Addresses synced started
2026-08-18 11:03:12.884 +05:30 [INF] Supplier Addresses synced completed. Status: 200 OK
2026-08-18 11:20:07.031 +05:30 [INF] Total Records Fetched for Supplier Details: 539
2026-08-18 11:20:07.033 +05:30 [INF] Supplier Details synced started
2026-08-18 11:21:07.512 +05:30 [ERR] Failed due to an issue in method "https://gateway.suppliersync.internal/api/supplier":
System.Net.Http.HttpRequestException: An error occurred while sending the request.
 ---> System.Net.Http.HttpIOException: The response ended prematurely. (ResponseEnded)
"""


def test_elapsed_is_derived_from_start_to_error(topology):
    assert parse(PRODUCTION_CASE, topology).facts["elapsed_seconds"] == 60.0


def test_rate_is_measured_from_the_log_not_assumed(topology):
    f = parse(PRODUCTION_CASE, topology).facts
    assert f["rate_source"] == "observed"
    # 39 records in 7s
    assert f["observed_seconds_per_record"] == pytest.approx(7 / 39, rel=1e-6)


def test_projection_shows_the_batch_could_not_have_finished(topology):
    f = parse(PRODUCTION_CASE, topology).facts
    assert f["projected_seconds"] == pytest.approx(539 * 7 / 39, rel=1e-6)
    assert f["projected_seconds"] > 90
    assert f["projection_exceeds_elapsed"] is True


def test_ceiling_is_detected(topology):
    f = parse(PRODUCTION_CASE, topology).facts
    assert f["ceiling_hit"] is True
    assert f["ceiling_seconds"] == 60.0


def test_baseline_rate_is_used_when_no_successful_batch_is_present(topology):
    text = """11:20:07 INF Total Records Fetched for Supplier Details: 539
11:20:07 INF Supplier Details synced started
11:21:07 ERR Failed
System.Net.Http.HttpIOException: The response ended prematurely.
"""
    f = parse(text, topology).facts
    assert f["rate_source"] == "baseline"
    assert f["projected_seconds"] is not None


def test_record_count_prefers_the_failing_batch(topology):
    f = parse(PRODUCTION_CASE, topology).facts
    assert f["record_count"] == 539


def test_small_batch_success_is_recorded(topology):
    assert parse(PRODUCTION_CASE, topology).facts["small_batches_succeeded"] is True


def test_midnight_rollover_does_not_produce_negative_elapsed(topology):
    text = """23:59:40 INF Total Records Fetched for Supplier Details: 400
23:59:40 INF Supplier Details synced started
00:00:40 ERR Failed
System.Net.Http.HttpIOException: The response ended prematurely.
"""
    assert parse(text, topology).facts["elapsed_seconds"] == 60.0


def test_error_without_a_start_line_warns_about_missing_elapsed(topology):
    text = "11:21:07 ERR Failed\nSystem.Exception: boom"
    result = parse(text, topology)
    assert result.facts["elapsed_seconds"] is None
    assert any("elapsed" in w for w in result.warnings)
