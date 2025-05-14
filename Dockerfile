# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt ./

# Install the application dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY record.py ./

# Expose the Prometheus port
EXPOSE 8000

# Run the application
CMD ["python", "record.py"]

