import streamlit as st
import streamlit.components.v1 as components
from main import create_agent
import utils
import os

#@st.cache_resource
def load_agent():
    """Initialize the RNA-seq agent with the LLM and database."""
    return create_agent()

agent = load_agent()

# Header
logo_url = "https://humantechnopole.it/wp-content/uploads/2020/10/01_HTlogo_pantone_colore.png"
st.image(logo_url, output_format="PNG", width=200)
st.title("🧬 RNA-seq Data Analysis Chatbot")
st.markdown("Ask a question about your RNA-seq data. The assistant can query the results and generate visual summaries.")

# Input form
query = st.text_input("Enter your question:")
submit = st.button("Submit")

if submit and query:
    with st.spinner("Working..."):
        try:
            answer, plot_filename = agent.ask(query)
            if answer:
                utils.render_cleaned_markdown(answer)
            if plot_filename and os.path.exists(plot_filename):
                components.html(open(plot_filename).read(), height=600)
        except Exception as e:
            st.error(f"Error: {e}")
