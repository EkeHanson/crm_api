import logging
import os
from pdfminer.high_level import extract_text
from docx import Document
from django.core.files.storage import default_storage
logger = logging.getLogger('job_applications')
import requests
import tempfile
import re

# Lazy initialization of SentenceTransformer
_model = None

def get_sentence_transformer_model():
    """Lazily load the SentenceTransformer model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer, util
            _model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
            logger.info("Loaded SentenceTransformer model")
        except Exception as e:
            logger.exception(f"Failed to load SentenceTransformer model: {str(e)}")
            raise RuntimeError("Unable to initialize sentence transformer model")
    return _model


def parse_resume(file_path):
    """Extract text from PDF or DOCX files."""
    try:
        logger.debug(f"Processing file_path: {file_path}")
        temp_file_path = None
        if file_path.startswith("http"):
            response = requests.get(file_path)
            if response.status_code != 200:
                logger.error(f"Failed to download file: {file_path}")
                return ""
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.write(response.content)
            temp_file.close()
            temp_file_path = temp_file.name
            full_path = temp_file_path
        else:
            normalized_path = file_path.lstrip("/").replace("media/", "", 1)
            logger.debug(f"Normalized path: {normalized_path}")
            if default_storage.exists(normalized_path):
                full_path = default_storage.path(normalized_path)
            else:
                logger.error(f"File does not exist: {normalized_path}")
                print(f"File does not exist: {normalized_path}")
                return ""

        logger.debug(f"Full path: {full_path}")

        ext = os.path.splitext(full_path)[1].lower()
        if ext == '.pdf':
            text = extract_text(full_path)
        elif ext in ['.docx', '.doc']:
            doc = Document(full_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
        else:
            logger.error(f"Unsupported file type: {ext}")
            text = ""

        # Clean up temporary file if created
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return text
    except Exception as e:
        logger.exception(f"Error parsing resume {file_path}: {str(e)}")
        # Clean up temporary file on error
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        return ""
    

def screen_resume(resume_text, job_description):
    """Compute similarity score between resume and job description."""
    try:
        if not resume_text or not job_description:
            logger.warning(f"Empty input: resume_text={bool(resume_text)}, job_description={bool(job_description)}")
            print(f"Empty input: resume_text={bool(resume_text)}, job_description={bool(job_description)}")
            return 0.0
        model = get_sentence_transformer_model()
        from sentence_transformers import util
        resume_emb = model.encode(resume_text, convert_to_tensor=True)
        jd_emb = model.encode(job_description, convert_to_tensor=True)
        score = util.pytorch_cos_sim(resume_emb, jd_emb).item()
        return round(score * 100, 2)
    except Exception as e:
        logger.exception(f"Error screening resume: {str(e)}")
        return 0.0
    



def extract_resume_fields(resume_text):
    """Extract structured fields from resume text using regex."""
    try:
        extracted_data = {
            "full_name": "",
            "email": "",
            "phone": "",
            "qualification": "",
            "experience": "",
            "knowledge_skill": ""
        }

        # Extract full name (simplified: assume first line or capitalized words at start)
        name_pattern = r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+'
        name_match = re.search(name_pattern, resume_text, re.MULTILINE)
        if name_match:
            extracted_data["full_name"] = name_match.group(0).strip()

        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, resume_text)
        if email_match:
            extracted_data["email"] = email_match.group(0)

        # Extract phone number
        phone_pattern = r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
        phone_match = re.search(phone_pattern, resume_text)
        if phone_match:
            extracted_data["phone"] = phone_match.group(0)

        # Extract qualifications (e.g., degrees)
        qual_pattern = r'\b(B\.Sc|Bachelor|M\.Sc|Master|Ph\.D|Diploma)\b.*?(?=\n|$|\b[A-Z])'
        qual_matches = re.findall(qual_pattern, resume_text, re.IGNORECASE)
        if qual_matches:
            extracted_data["qualification"] = ", ".join(qual_matches).strip()

        # Extract experience (e.g., years of experience or job titles with dates)
        exp_pattern = r'(\d{1,2}\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|work))|((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:@|at)\s*(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\(\d{4}\s*-\s*(?:\d{4}|Present)\))'
        exp_matches = re.findall(exp_pattern, resume_text, re.IGNORECASE)
        if exp_matches:
            experiences = []
            for match in exp_matches:
                if match[0]:
                    experiences.append(match[0])
                if match[1]:
                    experiences.append(match[1])
            extracted_data["experience"] = "; ".join(experiences).strip()

        # Extract skills (e.g., list of common skills)
        skills_pattern = r'\b(Python|Java|JavaScript|SQL|Project Management|Communication|Leadership|Teamwork|Problem Solving)\b'
        skills_matches = re.findall(skills_pattern, resume_text, re.IGNORECASE)
        if skills_matches:
            extracted_data["knowledge_skill"] = ", ".join(set(skills_matches)).strip()

        return extracted_data
    except Exception as e:
        logger.exception(f"Error extracting fields from resume: {str(e)}")
        return {}