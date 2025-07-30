import pandas as pd
import logging
import time
import random
from typing import List, Dict, Any
import streamlit as st

logger = logging.getLogger(__name__)

def invoke_with_retry(agent, input_dict: Dict[str, str], max_retries: int = 5) -> Dict[str, Any]:
    """Invoke agent with retry logic for 429 errors"""
    
    for attempt in range(max_retries):
        try:
            return agent.invoke(input_dict)
            
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a rate limit error
            if "429" in error_str or "rate limit" in error_str or "capacity" in error_str:
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    delay = min(2 ** attempt + random.uniform(0, 1), 30)
                    print(f"MistralAI at capacity, retrying in {delay:.1f}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    continue
                else:
                    # All retries exhausted - return in the same format as normal agent response
                    return {
                        "output": "MistralAI is currently at capacity. Please try again in a few moments.",
                        "intermediate_steps": []
                    }
            else:
                # Not a rate limit error, re-raise
                raise e
            
            
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
