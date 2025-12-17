from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from app.config import get_settings
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class TaskQueue:
    """Service for managing async job processing with Cloud Tasks"""
    
    def __init__(self, tasks_client: Optional[tasks_v2.CloudTasksClient] = None):
        self.client = tasks_client or tasks_v2.CloudTasksClient()
        self.queue_path = self.client.queue_path(
            settings.gcp_project_id,
            settings.gcp_location,
            settings.task_queue_name
        )
        logger.info("TaskQueue initialized")
    
    def create_extraction_task(
        self,
        job_id: str,
        pdf_id: str,
        request_data: Dict[str, Any],
        delay_seconds: int = 0
    ) -> str:
        """Create async extraction task"""
        task_name = f"extraction-{job_id}"
        
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.api_base_url}/api/v1/tasks/process-extraction",
                "headers": {
                    "Content-Type": "application/json",
                    "X-API-Key": settings.api_key
                },
                "body": json.dumps({
                    "job_id": job_id,
                    "pdf_id": pdf_id,
                    "request_data": request_data
                }).encode()
            }
        }
        
        if delay_seconds > 0:
            d = datetime.utcnow() + timedelta(seconds=delay_seconds)
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(d)
            task["schedule_time"] = timestamp
        
        try:
            response = self.client.create_task(
                request={"parent": self.queue_path, "task": task}
            )
            logger.info(f"Created extraction task for job {job_id}: {response.name}")
            return response.name
        except Exception as e:
            logger.error(f"Failed to create task for job {job_id}: {e}")
            raise
    
    def create_retry_task(
        self,
        job_id: str,
        retry_count: int,
        delay_seconds: int = 60
    ) -> str:
        """Create retry task with exponential backoff"""
        exponential_delay = delay_seconds * (2 ** retry_count)
        
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": f"{settings.api_base_url}/api/v1/tasks/retry-job",
                "headers": {
                    "Content-Type": "application/json",
                    "X-API-Key": settings.api_key
                },
                "body": json.dumps({
                    "job_id": job_id,
                    "retry_count": retry_count
                }).encode()
            }
        }
        
        d = datetime.utcnow() + timedelta(seconds=exponential_delay)
        timestamp = timestamp_pb2.Timestamp()
        timestamp.FromDatetime(d)
        task["schedule_time"] = timestamp
        
        try:
            response = self.client.create_task(
                request={"parent": self.queue_path, "task": task}
            )
            logger.info(f"Created retry task for job {job_id} (retry {retry_count}) with {exponential_delay}s delay")
            return response.name
        except Exception as e:
            logger.error(f"Failed to create retry task for job {job_id}: {e}")
            raise


task_queue = TaskQueue()
