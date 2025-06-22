# # job_application/utils.py
# import logging
# import os
# from pdfminer.high_level import extract_text
# from docx import Document
# from sentence_transformers import SentenceTransformer, util
# from django.conf import settings

# logger = logging.getLogger('job_applications')

# model = SentenceTransformer('all-MiniLM-L6-v2')

# def parse_resume(file_path):
#     """Extract text from PDF or DOCX files."""
#     try:
#         ext = os.path.splitext(file_path)[1].lower()
#         full_path = os.path.join(settings.MEDIA_ROOT, file_path)
#         if ext == '.pdf':
#             return extract_text(full_path)
#         elif ext in ['.docx', '.doc']:
#             doc = Document(full_path)
#             return '\n'.join([para.text for para in doc.paragraphs])
#         else:
#             logger.error(f"Unsupported file type: {ext}")
#             return ""
#     except Exception as e:
#         logger.exception(f"Error parsing resume {file_path}: {str(e)}")
#         return ""

# def screen_resume(resume_text, job_description):
#     """Compute similarity score between resume and job description."""
#     try:
#         if not resume_text or not job_description:
#             return 0.0
#         resume_emb = model.encode(resume_text, convert_to_tensor=True)
#         jd_emb = model.encode(job_description, convert_to_tensor=True)
#         score = util.pytorch_cos_sim(resume_emb, jd_emb).item()
#         return round(score * 100, 2)  # Convert to percentage
#     except Exception as e:
#         logger.exception(f"Error screening resume: {str(e)}")
#         return 0.0
# job_application/utils.py


import logging
import os
from pdfminer.high_level import extract_text
from docx import Document
from urllib.parse import urlparse
from django.conf import settings

logger = logging.getLogger('job_applications')

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
        # If file_path is a URL, get the path part
        if file_path.startswith("http"):
            file_path = urlparse(file_path).path  # e.g., "/media/application_documents/..."
        
        # Remove leading slash and "media/" if present
        normalized_path = file_path.replace("media/", "").lstrip("/")

        full_path = os.path.join(settings.MEDIA_ROOT, normalized_path)

        # print("full_path")
        # print(full_path)
        # print("full_path")

        ext = os.path.splitext(full_path)[1].lower()
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


# def parse_resume(file_path):
#     """Extract text from PDF or DOCX files."""
#     try:
#         ext = os.path.splitext(file_path)[1].lower()
#         full_path = os.path.join(settings.MEDIA_ROOT, file_path)

#         print("full_path")
#         print(full_path)
#         print("full_path")
        
#         if ext == '.pdf':
#             return extract_text(full_path)
#         elif ext in ['.docx', '.doc']:
#             doc = Document(full_path)
#             return '\n'.join([para.text for para in doc.paragraphs])
#         else:
#             logger.error(f"Unsupported file type: {ext}")
#             return ""
#     except Exception as e:
#         logger.exception(f"Error parsing resume {file_path}: {str(e)}")
#         return ""

def screen_resume(resume_text, job_description):
    """Compute similarity score between resume and job description."""
    try:
        if not resume_text or not job_description:
            return 0.0
        model = get_sentence_transformer_model()
        from sentence_transformers import util
        resume_emb = model.encode(resume_text, convert_to_tensor=True)
        jd_emb = model.encode(job_description, convert_to_tensor=True)
        score = util.pytorch_cos_sim(resume_emb, jd_emb).item()
        return round(score * 100, 2)  # Convert to percentage
    except Exception as e:
        logger.exception(f"Error screening resume: {str(e)}")
        return 0.0