# from locust import HttpUser, TaskSet, task, between
# from requests_toolbelt.multipart.encoder import MultipartEncoder
# import random
# import string
# from io import BytesIO


# def generate_unique_email():
#     return f"{random_string(8)}{random.randint(1000, 9999)}@test.com"


# def random_string(length=10):
#     return ''.join(random.choices(string.ascii_letters, k=length))


# def create_dummy_pdf():
#     return BytesIO(b"%PDF-1.4 Dummy PDF content\n%%EOF")


# class ApplicationTaskSet(TaskSet):
#     @task
#     def submit_application(self):
#         unique_link = "proliance-new-architecture-lead-8d16cd53"  # Ensure this matches a valid job in your DB
#         #unique_link = "proliance-registered-nurse-elderly-care-dc57ec2b"  # Ensure this matches a valid job in your DB

#         full_name = random_string(10)
#         email = generate_unique_email()
#         phone = "080" + ''.join(random.choices(string.digits, k=8))

#         resume_file = create_dummy_pdf()
#         resume_file.name = "resume.pdf"

#         multipart_data = MultipartEncoder(
#             fields={
#                 "unique_link": unique_link,
#                 "full_name": full_name,
#                 "email": email,
#                 "phone": phone,
#                 "qualification": "Ph.D. in Data Science",
#                 "experience": "4 years post PhD",
#                 "knowledge_skill": "Python, TensorFlow, Kubernetes",
#                 "date_of_birth": "1988-01-01",
#                 "cover_letter": "Experienced data scientist.",
#                 "resume_status": "true",  # Ensure this is treated as boolean in your Django serializer
#                 "documents[0][document_type]": "Curriculum Vitae (CV)",
#                 "documents[0][file]": ("resume.pdf", resume_file, "application/pdf"),
#             }
#         )

#         headers = {
#             "Content-Type": multipart_data.content_type
#         }

#         with self.client.post(
#             "/api/talent-engine-job-applications/applications/",
#             data=multipart_data,
#             headers=headers,
#             catch_response=True
#         ) as response:
#             if response.status_code == 201:
#                 response.success()
#             elif response.status_code == 400 and "already exists" in response.text:
#                 response.failure("Duplicate email detected: email already used for this job.")
#             elif response.status_code == 400 and "Expecting value" in response.text:
#                 response.failure("Invalid JSON or form data sent.")
#             elif response.status_code == 500:
#                 response.failure("Internal server error on the server (500).")
#             elif "WinError 10035" in response.text:
#                 response.failure("WinError 10035 - Non-blocking socket operation could not be completed.")
#             else:
#                 response.failure(f"Unexpected error: {response.status_code}, {response.text}")


# class WebsiteUser(HttpUser):
#     tasks = [ApplicationTaskSet]
#     wait_time = between(1, 3)
#     #host = "https://cmvp-api-v1.onrender.com" 
#     host = "http://localhost:9090"


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
    #host = "http://127.0.0.1:9090"  # Adjust to your actual host
    host = "https://cmvp-api-v1.onrender.com"  # Adjust to your actual host
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzUzMjcwODE5LCJpYXQiOjE3NTMyNjM2MTksImp0aSI6ImVjM2ZjNDExYzcxNTRhOTU4MTlkMDMzYTRiZDY2YmRhIiwidXNlcl9pZCI6MSwidGVuYW50X2lkIjoiMSIsInRlbmFudF9zY2hlbWEiOiJwcm9saWFuY2UifQ.A0rAdaLqaAf4j707KYr0QPUzgyMZgEzWvhaEV675lT0"
    
    
    def on_start(self):
        if not self.jwt_token:
            # Optionally fetch token dynamically here if needed
            self.token = "Bearer "
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
