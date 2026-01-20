# Dockerfile

FROM python:3.12

# Set working directory
WORKDIR /app

# Copy the app code to the container
COPY . .

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Run the FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8218", "--reload"]
