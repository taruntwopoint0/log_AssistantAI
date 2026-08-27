r"""Generate the eight demo log samples into ../samples/.

These are mock logs shaped after real BulkSuppliers Serilog output. The
gateway_timeout sample is the transcribed production case from 18 Aug 2026.

Run:  python gen_mock_logs.py

Tests import SCENARIOS and EXPECTED directly, so they do not need the files on
disk. The files exist so the dashboard can offer one-click sample loading and
so anyone can paste them by hand during a demo.
"""

from __future__ import annotations

from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parents[1] / "samples"


# The production case. Small batches succeed all day; every large batch dies at
# ~60s. The rate derived from the 39-record batch is what proves 539 records
# could never have finished inside that window.
GATEWAY_TIMEOUT = r"""2026-08-18 08:46:02.114 +05:30 [INF] BulkSuppliers worker cycle started
2026-08-18 08:46:02.119 +05:30 [INF] Total Records Fetched for Supplier Contacts: 2
2026-08-18 08:46:02.120 +05:30 [INF] Supplier Contacts synced started
2026-08-18 08:46:03.402 +05:30 [INF] Supplier Contacts synced completed. Status: 200 OK
2026-08-18 11:03:05.771 +05:30 [INF] Total Records Fetched for Supplier Addresses: 39
2026-08-18 11:03:05.772 +05:30 [INF] Supplier Addresses synced started
2026-08-18 11:03:12.884 +05:30 [INF] Supplier Addresses synced completed. Status: 200 OK
2026-08-18 11:20:07.031 +05:30 [INF] Total Records Fetched for Supplier Details: 539
2026-08-18 11:20:07.033 +05:30 [INF] Supplier Details synced started
2026-08-18 11:21:07.512 +05:30 [ERR] Failed due to an issue in method "https://gateway.suppliersync.internal/api/bulkSuppliers/v1.0/api/supplier":
System.Net.Http.HttpRequestException: An error occurred while sending the request.
 ---> System.Net.Http.HttpIOException: The response ended prematurely. (ResponseEnded)
   at System.Net.Http.HttpConnection.SendAsyncCore(HttpRequestMessage request, Boolean async, CancellationToken cancellationToken)
   --- End of inner exception stack trace ---
   at System.Net.Http.HttpClient.SendAsync(HttpRequestMessage request, HttpCompletionOption completionOption, CancellationToken cancellationToken)
   at SupplierSync.Api.FetchGalileoApi.GetAPIResponse(String url, String payload) in C:\src\SupplierSync\Api\FetchGalileoApi.cs:line 59
2026-08-18 11:21:07.640 +05:30 [INF] Email Trigger sent
"""


# Platform genuinely unavailable: every batch size fails identically and
# immediately. Size is not the variable, which is what separates this from the
# gateway case.
GALILEO_DOWN = r"""2026-08-19 09:15:01.220 +05:30 [INF] BulkSuppliers worker cycle started
2026-08-19 09:15:01.480 +05:30 [INF] Total Records Fetched for Supplier Contacts: 6
2026-08-19 09:15:01.481 +05:30 [INF] Supplier Contacts synced started
2026-08-19 09:15:02.109 +05:30 [ERR] Failed due to an issue in method "https://gateway.suppliersync.internal/api/bulkSuppliers/v1.0/api/contact":
System.Net.Http.HttpRequestException: Response status code does not indicate success: 503 (Service Unavailable).
   at System.Net.Http.HttpResponseMessage.EnsureSuccessStatusCode()
   at SupplierSync.Api.FetchGalileoApi.GetAPIResponse(String url, String payload) in C:\src\SupplierSync\Api\FetchGalileoApi.cs:line 71
2026-08-19 09:15:02.400 +05:30 [INF] Total Records Fetched for Supplier Details: 512
2026-08-19 09:15:02.401 +05:30 [INF] Supplier Details synced started
2026-08-19 09:15:03.077 +05:30 [ERR] Failed due to an issue in method "https://gateway.suppliersync.internal/api/bulkSuppliers/v1.0/api/supplier":
System.Net.Http.HttpRequestException: Response status code does not indicate success: 503 (Service Unavailable).
   at System.Net.Http.HttpResponseMessage.EnsureSuccessStatusCode()
   at SupplierSync.Api.FetchGalileoApi.GetAPIResponse(String url, String payload) in C:\src\SupplierSync\Api\FetchGalileoApi.cs:line 71
2026-08-19 09:15:03.310 +05:30 [INF] Email Trigger sent
"""


# Connect-level failure. Nothing ever reached the endpoint, so nothing beyond
# the network path can be assessed.
NETWORK_REFUSED = r"""2026-08-20 06:30:00.101 +05:30 [INF] BulkSuppliers worker cycle started
2026-08-20 06:30:00.355 +05:30 [INF] Total Records Fetched for Supplier Details: 214
2026-08-20 06:30:00.356 +05:30 [INF] Supplier Details synced started
2026-08-20 06:30:01.912 +05:30 [ERR] Failed due to an issue in method "https://gateway.suppliersync.internal/api/bulkSuppliers/v1.0/api/supplier":
System.Net.Http.HttpRequestException: An error occurred while sending the request.
 ---> System.Net.Sockets.SocketException (10061): No connection could be made because the target machine actively refused it. 10.42.18.7:443
   at System.Net.Sockets.Socket.AwaitableSocketAsyncEventArgs.ThrowException(SocketError error, CancellationToken cancellationToken)
   --- End of inner exception stack trace ---
   at SupplierSync.Api.FetchGalileoApi.GetAPIResponse(String url, String payload) in C:\src\SupplierSync\Api\FetchGalileoApi.cs:line 59
2026-08-20 06:30:02.044 +05:30 [INF] Email Trigger sent
"""


# The worker itself died mid-run. Nothing downstream is diagnosable from here.
SERVICE_CRASH = r"""2026-08-21 02:00:00.004 +05:30 [INF] BulkSuppliers worker cycle started
2026-08-21 02:00:00.240 +05:30 [INF] Total Records Fetched for Supplier Details: 402
2026-08-21 02:00:00.241 +05:30 [INF] Supplier Details synced started
2026-08-21 02:00:04.918 +05:30 [FTL] Unhandled exception. Application is shutting down.
System.NullReferenceException: Object reference not set to an instance of an object.
   at SupplierSync.Worker.SupplierSyncJob.MapContact(SupplierDto dto) in C:\src\SupplierSync\Worker\SupplierSyncJob.cs:line 137
   at SupplierSync.Worker.SupplierSyncJob.ExecuteAsync(CancellationToken stoppingToken) in C:\src\SupplierSync\Worker\SupplierSyncJob.cs:line 88
2026-08-21 02:00:05.002 +05:30 [WRN] Service SupplierSyncWorker is Stopped
"""


# Failed at the database step, before any outbound call was made.
DB_FAILURE = r"""2026-08-22 04:15:00.061 +05:30 [INF] BulkSuppliers worker cycle started
2026-08-22 04:15:00.062 +05:30 [INF] Supplier Details synced started
2026-08-22 04:15:30.774 +05:30 [ERR] Failed to fetch supplier details from Aldavar
Microsoft.Data.SqlClient.SqlException (0x80131904): Timeout expired. The timeout period elapsed prior to obtaining a connection from the pool. This may have occurred because all pooled connections were in use and max pool size was reached.
   at Microsoft.Data.SqlClient.SqlConnection.OnError(SqlException exception, Boolean breakConnection, Action`1 wrapCloseInAction)
   at SupplierSync.Data.AldavarRepository.GetSupplierDetails() in C:\src\SupplierSync\Data\AldavarRepository.cs:line 44
2026-08-22 04:15:30.900 +05:30 [INF] Email Trigger sent
"""


# Refused at the door, immediately, regardless of size.
AUTH_401 = r"""2026-08-23 07:45:00.310 +05:30 [INF] BulkSuppliers worker cycle started
2026-08-23 07:45:00.512 +05:30 [INF] Total Records Fetched for Supplier Details: 128
2026-08-23 07:45:00.513 +05:30 [INF] Supplier Details synced started
2026-08-23 07:45:01.884 +05:30 [ERR] Failed due to an issue in method "https://gateway.suppliersync.internal/api/bulkSuppliers/v1.0/api/supplier":
System.Net.Http.HttpRequestException: Response status code does not indicate success: 401 (Unauthorized).
   at System.Net.Http.HttpResponseMessage.EnsureSuccessStatusCode()
   at SupplierSync.Api.FetchGalileoApi.GetAPIResponse(String url, String payload) in C:\src\SupplierSync\Api\FetchGalileoApi.cs:line 71
2026-08-23 07:45:02.002 +05:30 [INF] Email Trigger sent
"""


# A clean cycle. The tool has to be willing to say nothing is wrong.
HEALTHY_RUN = r"""2026-08-24 08:46:02.114 +05:30 [INF] BulkSuppliers worker cycle started
2026-08-24 08:46:02.119 +05:30 [INF] Total Records Fetched for Supplier Contacts: 2
2026-08-24 08:46:02.120 +05:30 [INF] Supplier Contacts synced started
2026-08-24 08:46:03.402 +05:30 [INF] Supplier Contacts synced completed. Status: 200 OK
2026-08-24 08:46:04.010 +05:30 [INF] Total Records Fetched for Supplier Addresses: 39
2026-08-24 08:46:04.011 +05:30 [INF] Supplier Addresses synced started
2026-08-24 08:46:11.120 +05:30 [INF] Supplier Addresses synced completed. Status: 200 OK
2026-08-24 08:46:11.500 +05:30 [INF] Total Records Fetched for Supplier Details: 31
2026-08-24 08:46:11.501 +05:30 [INF] Supplier Details synced started
2026-08-24 08:46:16.640 +05:30 [INF] Supplier Details synced completed. Status: 200 OK
2026-08-24 08:46:16.700 +05:30 [INF] BulkSuppliers worker cycle completed
"""


# The most important demo case. Real error, matches no configured rule, and
# the tool declines to guess rather than reaching for the nearest runbook.
UNRECOGNISED = r"""2026-08-25 03:10:00.220 +05:30 [INF] Nightly reconciliation started
2026-08-25 03:10:01.455 +05:30 [ERR] Payload transform aborted for batch 7741
System.Text.Json.JsonException: '<' is an invalid start of a value. Path: $ | LineNumber: 0 | BytePositionInLine: 0.
   at System.Text.Json.ThrowHelper.ReThrowWithPath(ReadStack& state, JsonReaderException ex)
   at SupplierSync.Transform.PayloadMapper.Deserialize(String raw) in C:\src\SupplierSync\Transform\PayloadMapper.cs:line 96
2026-08-25 03:10:01.600 +05:30 [INF] Email Trigger sent
"""


SCENARIOS: dict[str, str] = {
    "gateway_timeout": GATEWAY_TIMEOUT,
    "galileo_down": GALILEO_DOWN,
    "network_refused": NETWORK_REFUSED,
    "service_crash": SERVICE_CRASH,
    "db_failure": DB_FAILURE,
    "auth_401": AUTH_401,
    "healthy_run": HEALTHY_RUN,
    "unrecognised": UNRECOGNISED,
}


# What each sample must conclude. Asserted by tests/test_scenarios.py.
EXPECTED: dict[str, dict[str, str]] = {
    "gateway_timeout": {"layer": "GatewayTimeout", "band": "Medium", "uncapped": "High"},
    "galileo_down":    {"layer": "GalileoDown",    "band": "Medium"},
    "network_refused": {"layer": "Network",        "band": "Medium"},
    "service_crash":   {"layer": "WindowsService", "band": "Medium"},
    "db_failure":      {"layer": "AldavarDB",      "band": "Medium"},
    "auth_401":        {"layer": "Auth",           "band": "Medium"},
    "healthy_run":     {"layer": "Healthy",        "band": "Medium"},
    "unrecognised":    {"layer": "Unknown",        "band": "Inconclusive"},
}


LABELS: dict[str, str] = {
    "gateway_timeout": "Gateway timeout (the production case)",
    "galileo_down": "Galileo unavailable",
    "network_refused": "Network refused",
    "service_crash": "Worker service crash",
    "db_failure": "Aldavar DB failure",
    "auth_401": "Credential rejected (401)",
    "healthy_run": "Healthy run",
    "unrecognised": "Unrecognised (declines to guess)",
}


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in SCENARIOS.items():
        path = SAMPLES_DIR / f"{name}.log"
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    print(f"\n{len(SCENARIOS)} samples written to {SAMPLES_DIR}")


if __name__ == "__main__":
    main()
