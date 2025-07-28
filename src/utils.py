import pandas as pd
import logging
import time
from typing import List
import streamlit as st

logger = logging.getLogger(__name__)

def retry_api_call(func, *args, max_retries=3, **kwargs):
    """Retry API calls with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                raise e
            
            # Check if it's a retryable error
            error_msg = str(e).lower()
            if "429" in error_msg or "rate limit" in error_msg or "service tier" in error_msg:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                logger.warning(f"API call failed (attempt {attempt + 1}), retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e  # Don't retry non-rate-limit errors
            
def render_cleaned_markdown(text):
    lines = text.strip().splitlines()
    cleaned = "\n".join(line.strip() for line in lines)
    st.markdown(cleaned)

def clean_generated_code(code):
        """Clean LLM generated code"""
        # Remove markdown code blocks
        if code.startswith("```python"):
            code = code.replace("```python", "").replace("```", "")
        if code.startswith("```"):
            code = code.replace("```", "")
        
        # Remove explanatory text before the code
        lines = code.strip().split('\n')
        clean_lines = []
        code_started = False
        
        for line in lines:
            if line.strip().startswith('import') or line.strip().startswith('fig') or code_started:
                code_started = True
                clean_lines.append(line)
        
        return '\n'.join(clean_lines)

def find_column(df: pd.DataFrame, possible_names: List[str]) -> str:
    """Find column by checking possible names (case insensitive)"""
    df_cols_lower = [col.lower() for col in df.columns]
    for name in possible_names:
        if name.lower() in df_cols_lower:
            return df.columns[df_cols_lower.index(name.lower())]
    return None
