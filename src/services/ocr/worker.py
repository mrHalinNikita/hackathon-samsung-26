from src.services.ocr.tasks import celery_app, process_image_task

app = celery_app