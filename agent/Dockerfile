FROM python:3.12-slim

WORKDIR /app

COPY agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install MCP server in isolated virtualenv (avoids uvicorn conflict with chainlit)
COPY mcp_polygon /opt/mcp_polygon
RUN python -m venv /opt/mcp_venv && \
    /opt/mcp_venv/bin/pip install --no-cache-dir /opt/mcp_polygon

COPY agent/ .

EXPOSE 8000

CMD ["chainlit", "run", "app.py", "--host", "0.0.0.0", "--port", "8000"]
