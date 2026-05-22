import os

from common.incident_report_repository import IncidentReportRepository
from common.response import json_response

INCIDENT_REPORTS_TABLE_NAME = os.environ.get("INCIDENT_REPORTS_TABLE_NAME", "")


def _incident_report_repository() -> IncidentReportRepository:
    return IncidentReportRepository(INCIDENT_REPORTS_TABLE_NAME)


def _get_report_id(event):
    path_parameters = event.get("pathParameters") or {}
    report_id = path_parameters.get("reportId")
    if isinstance(report_id, str) and report_id.strip():
        return report_id.strip()
    return None


def lambda_handler(event, context):
    if not INCIDENT_REPORTS_TABLE_NAME:
        return json_response(500, {"message": "Incident reports table is not configured."})

    report_id = _get_report_id(event)
    if not report_id:
        return json_response(400, {"message": "reportId path parameter is required."})

    report = _incident_report_repository().get_report(report_id)
    if report is None:
        return json_response(404, {"message": "Incident report not found."})

    return json_response(200, report)