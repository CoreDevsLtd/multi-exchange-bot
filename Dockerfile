FROM python:3.10-slim

WORKDIR /app

# Copy requirements file first
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the project
COPY . .

EXPOSE 8080

CMD ["python", "main_with_dashboard.py"]
