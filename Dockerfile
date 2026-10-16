FROM anasty17/mltb:latest

WORKDIR /app

# Avoid broad world-writable permissions. Runtime writable paths should be
# provided with narrowly scoped mounts/permissions where possible.
RUN python3 -m venv mltbenv

COPY requirements.txt .
RUN mltbenv/bin/pip install --no-cache-dir -r requirements.txt

# Secrets and runtime state are excluded by .dockerignore and must be mounted
# or supplied at runtime rather than baked into image layers.
COPY . .

RUN sed -i 's/\r$//' *.sh

CMD ["bash", "start.sh"]
