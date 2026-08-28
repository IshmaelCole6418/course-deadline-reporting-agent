from course_reporting.reporting_loop import CourseDelivery, create_client, run_reporting_loop


delivery = CourseDelivery.model_validate(
    {
        "course_id": "checkout-101",
        "lesson_id": "payment-statuses",
        "delivered_at": "2026-08-15T09:00:00Z",
        "learners": [
            {"learner_id": "learner-17", "due_at": "2026-08-16T09:00:00Z"},
            {
                "learner_id": "learner-24",
                "due_at": "2026-08-18T09:00:00Z",
                "submitted_at": "2026-08-16T12:30:00Z",
            },
        ],
    }
)

print(run_reporting_loop(delivery, client=create_client()).model_dump_json(indent=2))
