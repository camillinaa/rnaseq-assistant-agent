import logging
import json
import re
import os
from typing import List
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain.memory import ConversationBufferMemory

# from utils import retry_api_call

logger = logging.getLogger(__name__)

class RNAseqAgent:
    """Main RNAseq analysis agent"""

    def __init__(self, database, plotter, llm):
        self.db = database
        self.plotter = plotter
        self.llm = llm

        # Initialize memory
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )

        # Create tools
        self.tools = self._create_tools()

        # Initialize agent
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            memory=self.memory,
            return_intermediate_steps=True,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=15,
            max_execution_time=60,
            agent_kwargs={
                "system_message": 
                     """
                     You are an expert RNA-seq data analyst. Your role is to provide concrete answers using actual data from the database—never simulated or imagined.

                    YOU DO NOT HAVE ACCESS TO RNA-seq DATA IN YOUR TRAINING.  
                    You MUST use the available tools for EVERY query.

                    TOOLS (use in this order):
                    1. ALWAYS use `database_schema_tool` to inspect available tables and columns.
                    2. ALWAYS use `sql_query_tool` to retrieve actual data from the database.
                    3. Use `sample_column_values_tool` to explore possible values that the user might be referring to in columns before writing SQL, especially for categorical metadata (e.g., Batch, Condition).
                    4. Use `plot_tool` to generate visualizations based on query results.
                    
                    MANDATORY BEHAVIOR:
                    - Always use tools—NEVER guess, infer, or describe hypothetical data.
                    - Always query actual data and return the real values to the user.
                    - Always follow this sequence: `SQL_Query` → `Create_Plot` → `Final Answer`.
                    - Always return specific results: gene names, log2FC, adjusted p-values, pathway names, enrichment scores, etc.
                    - If SQL returns no rows, investigate by calling `database_schema_tool` or `sample_column_values_tool` to confirm the correct column names and available values.
                    - For differential expression or pathway analysis queries, always reference real tables using this naming format: dea_[sample_subset]_[comparison]_[analysis]_[gene_set]  
                    - For differential expression or pathway analysis queries, only consider statistically significant results (based on adjusted p-values or q-values).
                    - Always provide biological context in your interpretations, not just numbers.
                    
                    PLOTTING GUIDANCE:
                    - After each SQL query, decide whether a plot would help answer the question.
                    - Use `create_plot_tool` whenever helpful, and interpret the plot.
                    - Examples:
                    - Differential expression → volcano or MA plot
                    - Pathway enrichment → bar plot
                    - Value distributions → box plot or histogram
                    - Query results are automatically cached for plotting—just call the plot tool.

                    FORBIDDEN BEHAVIOR:
                    - NEVER provide p-values as a significance measure; always use adjusted p-values or q-values.
                    - NEVER describe the contents of a table without actually querying it.
                    - NEVER say “this data is in table X”—you must query the table and show real results.
                    - NEVER give instructions like “you can run this query”—you must execute the query.
                    - NEVER say you will create a plot and then fail to call the `create_plot_tool`.

                    EXAMPLES OF GOOD BEHAVIOR:

                    **User**: What are the top upregulated pathways?  
                    **Bad**: "The upregulated pathways can be found in the pathway_enrichment table."  
                    **Good**: "Let me query the pathway data...  
                    [Executes SQL]  
                    Top 5 upregulated pathways:  
                    1. Cell cycle regulation (enrichment: 4.2, padj: 0.001)  
                    2. DNA repair (3.8, 0.003)  
                    ..."

                    **User**: What are the top upregulated genes?  
                    **Good**:  
                    "Let me query the DE results...  
                    [Executes SQL]  
                    Top genes:  
                    1. GENE1 (log2FC: 3.2, padj: 0.001)  
                    ...  
                    [Creates volcano plot]  
                    This plot shows the DE profile, highlighting significant genes in red. It emphasizes..."
                    
                    **User**: Which genes are most highly expressed in batch 1 of the CD4 samples?  
                    **Good**:  
                    "Let me query the expression data filtered by batch 1...  
                    [Executes SQL with `WHERE batch = '1'`]  
                    → Query returns 0 rows.  
                    Let me double-check the available values for the `batch` column.  
                    [Calls `sample_column_values_tool` or executes `SELECT DISTINCT batch FROM CD4_expression`]  
                    → Finds values: 'b1', 'b2', 'b3'  
                    It looks like the correct value for batch 1 is actually 'b1'. Let me rerun the query.  
                    [Executes SQL with `WHERE batch = 'b1'`]  
                    Top expressed genes in batch b1:  
                    1. ACTB (normalized count: 12847)  
                    2. GAPDH (12532)  
                    ...  
                    [Creates plot]  
                    Here's a histogram showing gene expression distribution for batch b1..."

                    Always use the tools. Always return real results. Always visualize when helpful.

                    """

            }
        )

        # Connect to database
        if not self.db.connect():
            raise Exception("Failed to connect to database")

    def _create_tools(self) -> List[Tool]:
        """Create tools for the agent"""

        def sql_query_tool(query: str) -> str:
            """Execute SQL query against RNAseq database"""
            logger.info(f"EXECUTING SQL QUERY: {query}")
            result = self.db.execute_query(query)
            logger.info(f"QUERY RETURNED {len(result.get('data', []))} rows")

            if "error" in result:
                return f"Error: {result['error']}"

            # Store data for plotting
            if result["row_count"] > 0:
                store_result = self.plotter.store_query_data(result["data"], query)

            # Format result for LLM
            if result["row_count"] == 0:
                return "Query executed successfully but returned no results."

            # Limit output for large results
            max_rows = 20
            data = result["data"][:max_rows]

            output = f"Query returned {result['row_count']} rows. "
            if result["row_count"] > max_rows:
                output += f"Showing first {max_rows} rows:\n"
            else:
                output += "Here are all the results:\n"

            # Format as table-like string
            if data:
                columns = result["columns"]
                output += "\n" + " | ".join(columns) + "\n"
                output += "-" * (len(" | ".join(columns))) + "\n"

                for row in data:
                    row_values = [str(row.get(col, "")) for col in columns]
                    output += " | ".join(row_values) + "\n"

                output += f"\nThis is the actual data from the database. Use this to answer the user's question with specific details."
                output += f"\nNOTE: This data has been stored and is available for plotting if visualization would be helpful."

            return output

        def database_schema_tool(input_str: str) -> str:
            """Get information about database tables and their schemas"""
            logger.info("DATABASE_SCHEMA_TOOL called")  
            result = self.db.get_table_info()
            logger.info(f"Schema result: {result}")  

            if "error" in result:
                return f"Error: {result['error']}"

            output = "Available tables and their schemas:\n\n"
            for table_name, table_info in result["tables"].items():
                output += f"Table: {table_name}\n"
                output += "Columns:\n"
                for col in table_info["columns"]:
                    output += f"  - {col['name']} ({col['type']})\n"
                output += f"Sample query: {table_info['sample_query']}\n\n"

            return output
        
        def sample_column_values_tool(input_str: str) -> str:
            """Get a list of sample values from each column in each table"""
            logger.info("SAMPLE_COLUMN_VALUES_TOOL called")  

            output = "Sample values for selected columns:\n\n"

            for table_name in self.db.get_table_names():
                output += f"Table: {table_name}\n"
                try:
                    df = self.db.run(f"SELECT DISTINCT * FROM {table_name} LIMIT 20;")  # pull small sample
                    if isinstance(df, list):
                        df = pd.DataFrame(df)
                except Exception as e:
                    logger.error(f"Could not fetch data from {table_name}: {e}")
                    continue

                for col in df.columns:
                    unique_vals = df[col].dropna().unique()
                    if len(unique_vals) == 0:
                        continue
                    # Only show string-like values
                    if df[col].dtype == "object" or pd.api.types.is_categorical_dtype(df[col]):
                        vals_preview = ", ".join(map(str, unique_vals[:5]))  # limit to 5
                        output += f"  {col}: [{vals_preview}]\n"
                output += "\n"

            return output

        def plot_tool(plot_request: str) -> str:
            """Create plots from data. Format: 'plot_type|column_info|additional_params'"""
            try:
                if not self.plotter.last_query_data:
                    return "Error: No data available for plotting. Please run a SQL query first."

                # Parse the request - could be just "volcano" or "bar|title=My Title"  
                parts = plot_request.split("|")
                plot_type = parts[0].strip()
                
                # Extract any additional parameters
                additional_info = ""
                if len(parts) > 1:
                    additional_info = " ".join(parts[1:])

                result = self.plotter.create_plot(plot_type, additional_info=additional_info)

                if "error" in result:
                    return f"Plot creation failed: {result['error']}"

                return {
                    "success": True,
                    "summary": result["summary"],
                    "plot_filename": result["plot_filename"],
                    "generated_code": result["generated_code"],
                }

            except Exception as e:
                return f"Plot creation error: {str(e)}"
            
        return [
            Tool(
                name="SQL_Query",
                description="Execute SQL queries against the RNAseq database. Use this to get specific data. Input should be a valid SQL SELECT statement.",
                func=sql_query_tool
            ),
            Tool(
                name="Database_Schema",
                description="Get information about available tables and their column structures. Use this to understand what data is available before writing queries.",
                func=database_schema_tool
            ),
            Tool(
                name="Sample_Column_Values",
                description="Get sample values from each column in each table. Use this to match natural language references to possible values in the database.",
                func=sample_column_values_tool
            ),
            Tool(
                name="Create_Plot",
                description="Create plots. Input format: 'plot_type' or 'plot_type|additional_parameters'. Example: 'bar' or 'volcano|title=My Plot'",
                func=plot_tool
            )
        ]

    def ask(self, question: str) -> str:
        """Process user question and return response"""
        try:
            # Add system context about RNAseq analysis
            system_context = """
            You are an expert RNAseq data analyst. You have access to an RNAseq database with tools to:
            1. Query the database using SQL
            2. Get database schema information
            3. Create visualizations

            When analyzing RNAseq data:
            - Always check the database schema first if you're unsure about available tables/columns
            - Unless the user specifies it, limit your queries to 5 rows to avoid overwhelming output
            - Use appropriate significance thresholds (e.g., padj < 0.05, |log2fc| > 1)
            - Provide biological context in your interpretations

            Start by understanding what data is available, then query appropriately to answer the question.
            """

            # Run the agent
            contextualized_question = f"{system_context}\n\nUser question: {question}"
            result = self.agent({"input": contextualized_question})
            answer = result.get("output", "")

            # Search intermediate steps for plot_filename
            plot_filename = None
            for action, observation in result.get("intermediate_steps", []):
                if isinstance(observation, dict) and "plot_filename" in observation:
                    plot_filename = observation["plot_filename"]
                    break

            return answer, plot_filename
            
        except Exception as e:
            logger.error(f"Agent execution error: {e}")
            return f"I encountered an error while processing your question: {str(e)}"

    def close(self):
        """Clean up resources"""
        self.db.close()
