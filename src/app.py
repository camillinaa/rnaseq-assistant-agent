import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
import os
import uuid
import smtplib
from email.message import EmailMessage

# Import your agent and utils
from main import create_agent  # corrected from agent.py to main.py
import utils

# Instantiate your agent
agent = create_agent()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "RNA-seq Chatbot"

app.layout = dbc.Container([

    html.Div([
        html.Img(src="https://humantechnopole.it/wp-content/uploads/2020/10/01_HTlogo_pantone_colore.png", 
                 style={"width": "200px"}),
        html.H2("🧬 RNA-seq Data Analysis Chatbot", className="my-3"),
        html.P("Ask a question about your RNA-seq data. The assistant can query the results and generate visual summaries.")
    ]),

    html.Div(id='chat-window', children=[], style={
        'height': '60vh', 'overflowY': 'auto', 'padding': '10px', 'border': '1px solid #ccc', 'marginBottom': '15px'
    }),

    dbc.InputGroup([
        dbc.Input(id='user-input', placeholder='Enter your question...', type='text', debounce=True),
        dbc.Button('Submit', id='send-button', color='primary', n_clicks=0)
    ], className="mb-4"),

    dcc.Store(id='chat-history', data=[]),
    html.Div("⚠️ Conversations are not saved and will reset if refreshed.", className="text-muted"),

    html.Div(
        id="support-drawer",
        children=[
            # Support tab (at top of the drawer now)
            html.Div(
                "💬 Support",
                id="open-support-form",
                style={
                    "textAlign": "center",
                    "padding": "6px 24px",
                    "fontSize": "14px",
                    "backgroundColor": "#007bff",
                    "color": "white",
                    "borderTopLeftRadius": "12px",
                    "borderTopRightRadius": "12px",
                    "cursor": "pointer",
                    "userSelect": "none"
                }
            ),

            # The form body, revealed on expand
            html.Div([
                html.H5("Support Request", className="card-title", style={"marginTop": "10px"}),
                dbc.Input(id="support-email", placeholder="Your email", type="email", className="mb-2"),
                dbc.Textarea(id="support-message", placeholder="Describe your issue...", className="mb-2"),
                dbc.Button("Send", id="send-support", color="info", className="mb-2"),
                html.Div(id="support-status", className="text-muted", style={"fontSize": "0.9em"})
            ],
            id="support-drawer-body",
            style={"display": "none", "padding": "0 20px"})
        ],
        style={
            "position": "fixed",
            "bottom": "0",
            "left": "50%",
            "transform": "translateX(-50%)",
            "width": "320px",
            "height": "30px",  # collapsed height
            "backgroundColor": "white",
            "boxShadow": "0 -2px 8px rgba(0, 0, 0, 0.15)",
            "borderTopLeftRadius": "12px",
            "borderTopRightRadius": "12px",
            "overflow": "hidden",
            "zIndex": "1002",
            "transition": "height 0.4s ease"
        }
    )

])


def create_bot_message(message, html_content=None):
    children = [
        html.Div(message, style={
            'backgroundColor': '#f1f0f0', 'borderRadius': '15px', 'padding': '10px',
            'marginBottom': '5px', 'maxWidth': '75%', 'display': 'inline-block'
        })
    ]
    if html_content:
        children.append(html.Iframe(srcDoc=html_content, height="600", style={"width": "100%", "border": "none"}))
    return html.Div(children, style={"textAlign": "left", "marginBottom": "15px"})


def create_user_message(message):
    return html.Div([
        html.Div(message, style={
            'backgroundColor': '#007bff', 'color': 'white', 'borderRadius': '15px', 'padding': '10px',
            'marginBottom': '5px', 'maxWidth': '75%', 'marginLeft': 'auto', 'display': 'inline-block'
        })
    ], style={"textAlign": "right", "marginBottom": "15px"})


@app.callback(
    Output('chat-window', 'children'),
    Output('chat-history', 'data'),
    Output('user-input', 'value'),
    Input('send-button', 'n_clicks'),
    Input('user-input', 'n_submit'),
    State('user-input', 'value'),
    State('chat-history', 'data'),
    prevent_initial_call=True
)
def update_chat(n_clicks, n_submit, user_input, chat_history):
    if not user_input:
        return dash.no_update, dash.no_update, dash.no_update

    chat_history.append({"role": "user", "content": user_input})

    try:
        answer, plot_filename = agent.ask(user_input)
        if plot_filename and os.path.exists(plot_filename):
            with open(plot_filename, "r") as f:
                html_plot = f.read()
        else:
            html_plot = None
        chat_history.append({"role": "bot", "content": answer, "html_plot": html_plot})
    except Exception as e:
        answer = f"Error: {e}"
        chat_history.append({"role": "bot", "content": answer, "html_plot": None})

    displayed_chat = []
    for msg in chat_history:
        if msg["role"] == "user":
            displayed_chat.append(create_user_message(msg["content"]))
        elif msg["role"] == "bot":
            displayed_chat.append(create_bot_message(msg["content"], msg.get("html_plot")))

    return displayed_chat, chat_history, ""


@app.callback(
    Output("support-drawer", "style"),
    Output("support-drawer-body", "style"),
    Input("open-support-form", "n_clicks"),
    State("support-drawer", "style"),
    prevent_initial_call=True
)
def slide_support_drawer(n_clicks, style):
    if style["height"] == "30px":
        style["height"] = "320px"
        return style, {"display": "block", "padding": "0 20px"}
    else:
        style["height"] = "30px"
        return style, {"display": "none"}


@app.callback(
    Output("support-status", "children"),
    Input("send-support", "n_clicks"),
    State("support-email", "value"),
    State("support-message", "value"),
    prevent_initial_call=True
)
def send_support_email(n_clicks, email, message):
    if not email or not message:
        return "Please fill in both fields."

    try:
        msg = EmailMessage()
        msg.set_content(f"Support request from: {email}\n\nMessage:\n{message}")
        msg["Subject"] = "RNA-seq Chatbot Support Request"
        msg["From"] = email
        msg["To"] = "camilla.callierotti@fht.org"

        with smtplib.SMTP("localhost") as server:
            server.send_message(msg)

        return "✅ Your message has been sent."
    except Exception as e:
        return f"❌ Failed to send message: {str(e)}"


if __name__ == '__main__':
    app.run(debug=True)
