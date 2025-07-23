from locust import HttpUser, task, between
import random
import string
import json
import uuid

def random_string(length=8):
    return ''.join(random.choices(string.ascii_letters, k=length))

def generate_title():
    return f"Test Job {random.randint(1000, 9999)}"

class RequisitionTestUser(HttpUser):
    wait_time = between(1, 3)
    host = "http://127.0.0.1:9090"  # Adjust to your actual host
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzUzMjY5NDMzLCJpYXQiOjE3NTMyNjIyMzMsImp0aSI6ImE1YWE4Njg1NTkzNTQwNmRhMWI5NDQ3MjA0OWMzODJkIiwidXNlcl9pZCI6MSwidGVuYW50X2lkIjoiMiIsInRlbmFudF9zY2hlbWEiOiJwcm9saWFuY2UifQ.VrYBqvfzpFGiW6VOGI6qO8QrVWbonAHpLRoTZLQIOrQ"  # 🔐 Insert your valid token here

    def on_start(self):
        if not self.jwt_token:
            # Optionally fetch token dynamically here if needed
            self.token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzUzMjY5NDMzLCJpYXQiOjE3NTMyNjIyMzMsImp0aSI6ImE1YWE4Njg1NTkzNTQwNmRhMWI5NDQ3MjA0OWMzODJkIiwidXNlcl9pZCI6MSwidGVuYW50X2lkIjoiMiIsInRlbmFudF9zY2hlbWEiOiJwcm9saWFuY2UifQ.VrYBqvfzpFGiW6VOGI6qO8QrVWbonAHpLRoTZLQIOrQ"  # Replace manually or automate
        else:
            self.token = f"Bearer {self.jwt_token}"

    @task
    def get_requisitions(self):
        headers = {
            "Authorization": self.token
        }
        with self.client.get(
            "/api/talent-engine/requisitions/",
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"GET failed: {response.status_code}, {response.text}")

    @task
    def post_requisition(self):
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json"
        }

        requisition_data = {
            "title": generate_title(),
            "status": "pending",
            "role": "staff",
            "job_type": "full_time",
            "location_type": "on_site",
            "company_name": "Test Company",
            "company_address": "123 Test St.",
            "job_location": "Remote Office",
            "interview_location": "HQ - Conf Room",
            "salary_range": "100,000 - 120,000",
            "job_description": "Job description goes here.",
            "number_of_candidates": 3,
            "qualification_requirement": "Bachelor's Degree",
            "experience_requirement": "2+ years",
            "knowledge_requirement": "Python, Django",
            "reason": "Backfill position",
            "deadline_date": "2025-12-31",
            "start_date": "2025-11-01",
            "responsibilities": [
                "Write clean code", "Attend meetings"
            ],
            "documents_required": [
                "CV", "Cover Letter"
            ],
        }

        with self.client.post(
            "/api/talent-engine/requisitions/",
            data=json.dumps(requisition_data),
            headers=headers,
            catch_response=True
        ) as response:
            if response.status_code == 201:
                response.success()
            elif response.status_code == 400:
                response.failure(f"POST validation error: {response.text}")
            else:
                response.failure(f"POST failed: {response.status_code}, {response.text}")
