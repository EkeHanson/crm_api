# job_application/utils.py
import logging
import os
from pdfminer.high_level import extract_text
from docx import Document
from sentence_transformers import SentenceTransformer, util
from django.conf import settings

logger = logging.getLogger('job_applications')

model = SentenceTransformer('all-MiniLM-L6-v2')

def parse_resume(file_path):
    """Extract text from PDF or DOCX files."""
    try:
        ext = os.path.splitext(file_path)[1].lower()
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        if ext == '.pdf':
            return extract_text(full_path)
        elif ext in ['.docx', '.doc']:
            doc = Document(full_path)
            return '\n'.join([para.text for para in doc.paragraphs])
        else:
            logger.error(f"Unsupported file type: {ext}")
            return ""
    except Exception as e:
        logger.exception(f"Error parsing resume {file_path}: {str(e)}")
        return ""

def screen_resume(resume_text, job_description):
    """Compute similarity score between resume and job description."""
    try:
        if not resume_text or not job_description:
            return 0.0
        resume_emb = model.encode(resume_text, convert_to_tensor=True)
        jd_emb = model.encode(job_description, convert_to_tensor=True)
        score = util.pytorch_cos_sim(resume_emb, jd_emb).item()
        return round(score * 100, 2)  # Convert to percentage
    except Exception as e:
        logger.exception(f"Error screening resume: {str(e)}")
        return 0.0