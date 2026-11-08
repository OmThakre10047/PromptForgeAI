FROM python:3.12-slim

# g++ compiles AI-generated C++ solutions inside the sandbox.
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY problems ./problems

RUN useradd --create-home runner && mkdir -p /app/data && chown runner /app/data
USER runner
ENV DATA_DIR=/app/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
