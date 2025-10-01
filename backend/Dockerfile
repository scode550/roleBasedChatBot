# Use a stable Python base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install system dependencies needed for llama-cpp-python
# This is crucial for building the library from source if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies, including llama-cpp-python with specific build arguments
# CMAKE_ARGS ensures llama.cpp is built with hardware optimizations if available
RUN CMAKE_ARGS="-DLLAMA_CUBLAS=OFF -DLLAMA_CUDA_F16=OFF" pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8000

# Define the command to run the application
# We use --host 0.0.0.0 to make it accessible from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
