import gradio as gr
import requests

# Base URL for the FastAPI server (assumes same process for mounting)
BASE_URL = "http://localhost:8000"

with gr.Blocks() as demo:
    # Global state for conversation ID
    conversation_id_state = gr.State(value="")

    with gr.Tab("Submit Incident"):
        description = gr.Textbox(label="Incident Description", lines=3)
        submit_btn = gr.Button("Submit")
        submit_output = gr.JSON(label="Submission Result")

        def submit_incident(desc):
            payload = {"description": desc, "payload": {}}
            resp = requests.post(f"{BASE_URL}/incident", json=payload)
            if resp.ok:
                data = resp.json()
                # Store conversation_id for later tabs
                conversation_id_state.value = data["conversation_id"]
                return data
            else:
                return {"error": resp.text}
        submit_btn.click(fn=submit_incident, inputs=description, outputs=submit_output)

    with gr.Tab("Result"):
        refresh_btn = gr.Button("Refresh Result")
        result_output = gr.JSON(label="Result")

        def fetch_result():
            conv_id = conversation_id_state.value
            if not conv_id:
                return {"error": "No conversation ID"}
            resp = requests.get(f"{BASE_URL}/incident/{conv_id}/result")
            return resp.json() if resp.ok else {"error": resp.text}
        refresh_btn.click(fn=fetch_result, inputs=None, outputs=result_output)

    with gr.Tab("HITL Approval"):
        status_output = gr.Markdown(label="Pending Status")
        approve_btn = gr.Button("Approve")
        reject_btn = gr.Button("Reject")
        hitl_output = gr.JSON(label="HITL Response")

        def check_pending():
            conv_id = conversation_id_state.value
            if not conv_id:
                return "No conversation ID"
            pending = requests.get(f"{BASE_URL}/incident/{conv_id}/result").json().get("state", {})
            return "Pending human approval required" if pending.get("hitl_required", False) else "No pending actions"
        def approve(conv_id):
            resp = requests.post(f"{BASE_URL}/incident/{conv_id}/approve")
            return resp.json() if resp.ok else {"error": resp.text}
        def reject(conv_id):
            resp = requests.post(f"{BASE_URL}/incident/{conv_id}/reject")
            return resp.json() if resp.ok else {"error": resp.text}

        status_output.change(fn=check_pending, inputs=None, outputs=status_output)
        approve_btn.click(fn=approve, inputs=conversation_id_state, outputs=hitl_output)
        reject_btn.click(fn=reject, inputs=conversation_id_state, outputs=hitl_output)

__all__ = ["demo"]
