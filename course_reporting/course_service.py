from fastapi import FastAPI

from .reporting_loop import CourseDelivery, EducatorReport, create_client, run_reporting_loop

service = FastAPI(title="Course deadline reporting")


@service.post("/reports", response_model=EducatorReport)
def create_report(delivery: CourseDelivery) -> EducatorReport:
    return run_reporting_loop(delivery, client=create_client())
