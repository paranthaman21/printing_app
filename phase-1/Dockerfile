# Use an official lightweight Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy only the requirements file first to build the cache
COPY requirements.txt .

# Install dependencies without using the cache
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual application files
COPY backend/ /app/backend/
COPY customer/ /app/customer/
COPY static/ /app/static/

# Make sure an `uploads` folder exists for saving documents locally
RUN mkdir -p /app/uploads && chmod 777 /app/uploads

# Expose port 5000 to the outside world
EXPOSE 5000

# Backend is designed to run from within the backend/ folder
WORKDIR /app/backend

# Start the Flask app
CMD ["python", "app.py"]
