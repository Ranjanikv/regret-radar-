FROM exasol/script-language-container:latest
# Install the sentence‑transformers library (lightweight model)
RUN pip install --no-cache-dir sentence-transformers==2.2.2
# Copy the helper script into the container
COPY embed.py /opt/embedding/embed.py
